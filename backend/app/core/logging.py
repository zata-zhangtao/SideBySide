"""
Unified logging infrastructure for the SideBySide backend application.

This module provides a centralized logging system with the following features:
- Environment-based formatting (text for dev, JSON for production)
- Request context tracking (request_id, user_id, session_id)
- LLM-specific logging utilities
- Performance metrics decorators
- Log file rotation

Usage:
    Basic logging:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("This is an info message")
        logger.error("This is an error", exc_info=True)

    With request context (automatically injected in middleware):
        logger.info("Processing request")  # Will include request_id, user_id, etc.

    LLM logging:
        from app.core.logging import log_llm_call

        @log_llm_call
        async def call_llm(prompt: str) -> str:
            # Your LLM call here
            return response

    Performance logging:
        from app.core.logging import log_execution

        @log_execution
        def expensive_function():
            # Your code here
            pass
"""

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Context variables for request tracking
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
session_id_ctx: ContextVar[Optional[int]] = ContextVar("session_id", default=None)


class ContextFilter(logging.Filter):
    """
    Logging filter that injects contextual information into log records.
    Adds request_id, user_id, and session_id from context variables.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get()
        record.session_id = session_id_ctx.get()
        return True


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs log records as JSON.
    Suitable for production environments and log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        from datetime import timezone
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context information if available
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id") and record.user_id:
            log_data["user_id"] = record.user_id
        if hasattr(record, "session_id") and record.session_id:
            log_data["session_id"] = record.session_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "request_id",
                "user_id",
                "session_id",
            ]:
                log_data[key] = value

        return json.dumps(log_data)


class ColoredTextFormatter(logging.Formatter):
    """
    Formatter that outputs human-readable colored text.
    Suitable for development environments.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            )

        # Build context string
        context_parts = []
        if hasattr(record, "request_id") and record.request_id:
            context_parts.append(f"req:{record.request_id[:8]}")
        if hasattr(record, "user_id") and record.user_id:
            context_parts.append(f"user:{record.user_id}")
        if hasattr(record, "session_id") and record.session_id:
            context_parts.append(f"sess:{record.session_id}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""

        # Format the message
        log_format = f"%(asctime)s %(levelname)s [%(name)s]{context_str} %(message)s"
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class PlainTextFormatter(logging.Formatter):
    """
    Formatter that outputs human-readable plain text without colors.
    Suitable for file output where ANSI color codes are not desired.
    Includes request context (request_id, user_id, session_id) like ColoredTextFormatter.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build context string (same as ColoredTextFormatter but without colors)
        context_parts = []
        if hasattr(record, "request_id") and record.request_id:
            context_parts.append(f"req:{record.request_id[:8]}")
        if hasattr(record, "user_id") and record.user_id:
            context_parts.append(f"user:{record.user_id}")
        if hasattr(record, "session_id") and record.session_id:
            context_parts.append(f"sess:{record.session_id}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""

        # Format the message without color codes
        log_format = f"%(asctime)s %(levelname)s [%(name)s]{context_str} %(message)s"
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class LoggerManager:
    """
    Singleton manager for the logging configuration.
    Handles initialization and provides logger instances.
    """

    _instance: Optional["LoggerManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(
        self,
        log_level: str = "INFO",
        log_format: str = "text",
        log_file_path: Optional[str] = None,
        log_rotation_size: int = 10 * 1024 * 1024,  # 10MB
        log_rotation_count: int = 5,
    ) -> None:
        """
        Initialize the logging system.

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_format: Format type ('text' or 'json')
            log_file_path: Path to log file (None = console only)
            log_rotation_size: Max size in bytes before rotation (default 10MB)
            log_rotation_count: Number of backup files to keep (default 5)
        """
        if self._initialized:
            return

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        # Remove existing handlers
        root_logger.handlers.clear()

        # Choose formatter based on format type
        if log_format.lower() == "json":
            # JSON format: same for console and file
            console_formatter = JSONFormatter()
            file_formatter = JSONFormatter()
        else:
            # Text format: colored for console, plain for file
            console_formatter = ColoredTextFormatter()
            # Plain text formatter for files (no color codes, but includes context)
            file_formatter = PlainTextFormatter()

        # Console handler (always uses colored/json formatter)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(ContextFilter())
        root_logger.addHandler(console_handler)

        # File handler with rotation (if log file path is provided)
        if log_file_path:
            log_path = Path(log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=log_rotation_size,
                backupCount=log_rotation_count,
                encoding="utf-8",
            )
            # Use plain formatter for file to avoid color codes
            file_handler.setFormatter(file_formatter)
            file_handler.addFilter(ContextFilter())
            root_logger.addHandler(file_handler)

        self._initialized = True

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance with the given name.

        Args:
            name: Logger name (typically __name__ of the calling module)

        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)


# Singleton instance
_manager = LoggerManager()


def initialize_logging(
    log_level: str = "INFO",
    log_format: str = "text",
    log_file_path: Optional[str] = None,
    log_rotation_size: int = 10 * 1024 * 1024,
    log_rotation_count: int = 5,
) -> None:
    """
    Initialize the logging system (call once at application startup).

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('text' or 'json')
        log_file_path: Path to log file (None = console only)
        log_rotation_size: Max size in bytes before rotation (default 10MB)
        log_rotation_count: Number of backup files to keep (default 5)
    """
    _manager.initialize(
        log_level=log_level,
        log_format=log_format,
        log_file_path=log_file_path,
        log_rotation_size=log_rotation_size,
        log_rotation_count=log_rotation_count,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return _manager.get_logger(name)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
) -> None:
    """
    Set the current request context for logging.

    Args:
        request_id: Unique request identifier
        user_id: Current user ID
        session_id: Current session ID
    """
    if request_id is not None:
        request_id_ctx.set(request_id)
    if user_id is not None:
        user_id_ctx.set(user_id)
    if session_id is not None:
        session_id_ctx.set(session_id)


def clear_request_context() -> None:
    """Clear the current request context."""
    request_id_ctx.set(None)
    user_id_ctx.set(None)
    session_id_ctx.set(None)


def log_execution(func: Callable) -> Callable:
    """
    Decorator that logs function execution time and basic info.

    Example:
        @log_execution
        def expensive_function():
            # Your code here
            pass
    """
    logger = get_logger(func.__module__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__qualname__
        logger.debug(f"Executing {func_name}")
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(
                f"Completed {func_name}",
                extra={"execution_time_ms": round(elapsed * 1000, 2)},
            )
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed {func_name}: {str(e)}",
                extra={"execution_time_ms": round(elapsed * 1000, 2)},
                exc_info=True,
            )
            raise

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = func.__qualname__
        logger.debug(f"Executing {func_name}")
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(
                f"Completed {func_name}",
                extra={"execution_time_ms": round(elapsed * 1000, 2)},
            )
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed {func_name}: {str(e)}",
                extra={"execution_time_ms": round(elapsed * 1000, 2)},
                exc_info=True,
            )
            raise

    # Return appropriate wrapper based on whether function is async
    import inspect

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper


def log_llm_call(func: Callable) -> Callable:
    """
    Decorator that logs LLM API calls with detailed information.

    Logs:
    - Function being called
    - Execution time
    - Model name (if available in result)
    - Token usage (if available in result)
    - Errors

    Example:
        @log_llm_call
        async def call_openai(prompt: str) -> dict:
            # Your LLM call here
            return response
    """
    logger = get_logger(func.__module__)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = func.__qualname__
        logger.info(f"LLM call started: {func_name}")
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time

            # Extract LLM-specific info from result if available
            extra_info: Dict[str, Any] = {"execution_time_ms": round(elapsed * 1000, 2)}

            # Try to extract model and token info
            if isinstance(result, dict):
                if "model" in result:
                    extra_info["model"] = result["model"]
                if "usage" in result and isinstance(result["usage"], dict):
                    extra_info["prompt_tokens"] = result["usage"].get("prompt_tokens")
                    extra_info["completion_tokens"] = result["usage"].get(
                        "completion_tokens"
                    )
                    extra_info["total_tokens"] = result["usage"].get("total_tokens")

            logger.info(f"LLM call completed: {func_name}", extra=extra_info)
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"LLM call failed: {func_name} - {str(e)}",
                extra={"execution_time_ms": round(elapsed * 1000, 2)},
                exc_info=True,
            )
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_name = func.__qualname__
        logger.info(f"LLM call started: {func_name}")
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # Extract LLM-specific info from result if available
            extra_info: Dict[str, Any] = {"execution_time_ms": round(elapsed * 1000, 2)}

            if isinstance(result, dict):
                if "model" in result:
                    extra_info["model"] = result["model"]
                if "usage" in result and isinstance(result["usage"], dict):
                    extra_info["prompt_tokens"] = result["usage"].get("prompt_tokens")
                    extra_info["completion_tokens"] = result["usage"].get(
                        "completion_tokens"
                    )
                    extra_info["total_tokens"] = result["usage"].get("total_tokens")

            logger.info(f"LLM call completed: {func_name}", extra=extra_info)
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"LLM call failed: {func_name} - {str(e)}",
                extra={"execution_time_ms": round(elapsed * 1000, 2)},
                exc_info=True,
            )
            raise

    # Return appropriate wrapper based on whether function is async
    import inspect

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class LogContext:
    """
    Context manager for temporary logging context.

    Example:
        with LogContext(request_id="abc123", user_id=42):
            logger.info("This will include request_id and user_id")
    """

    def __init__(
        self,
        request_id: Optional[str] = None,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self.prev_request_id = None
        self.prev_user_id = None
        self.prev_session_id = None

    def __enter__(self):
        # Save previous context
        self.prev_request_id = request_id_ctx.get()
        self.prev_user_id = user_id_ctx.get()
        self.prev_session_id = session_id_ctx.get()

        # Set new context
        set_request_context(
            request_id=self.request_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous context
        set_request_context(
            request_id=self.prev_request_id,
            user_id=self.prev_user_id,
            session_id=self.prev_session_id,
        )
