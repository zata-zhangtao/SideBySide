from __future__ import annotations

import os
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .core.config import settings
from .core.logging import initialize_logging, get_logger, set_request_context, clear_request_context
from .db import init_db
from .routers import auth, users, wordlists, sessions, leaderboard, reports

# Initialize logger for this module
logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that injects request context into logging.
    Automatically adds request_id to all logs within a request.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Set request context for logging
        set_request_context(request_id=request_id)

        # Add request_id to request state for access in endpoints
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            # Add request ID to response headers for tracing
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Clear context after request
            clear_request_context()


def create_app() -> FastAPI:
    # Initialize logging system first
    initialize_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        log_file_path=settings.LOG_FILE_PATH,
        log_rotation_size=settings.LOG_ROTATION_SIZE,
        log_rotation_count=settings.LOG_ROTATION_COUNT,
    )

    app = FastAPI(title="SideBySide API", version="0.1.0")

    # Add request context middleware (before CORS)
    app.add_middleware(RequestContextMiddleware)

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Startup event
    @app.on_event("startup")
    async def startup_event():
        logger.info("Application startup: SideBySide API v0.1.0")
        logger.info(f"Environment: LOG_LEVEL={settings.LOG_LEVEL}, LOG_FORMAT={settings.LOG_FORMAT}")

    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutdown")

    # Initialize DB (create tables if needed)
    init_db()
    logger.info("Database initialized")

    # Routers
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(users.router, prefix="/api", tags=["users"])
    app.include_router(wordlists.router, prefix="/api", tags=["wordlists"])
    app.include_router(sessions.router, prefix="/api", tags=["sessions"])
    app.include_router(leaderboard.router, prefix="/api", tags=["leaderboard"])
    app.include_router(reports.router, prefix="/api", tags=["reports"])

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

