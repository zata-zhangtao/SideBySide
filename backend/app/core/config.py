from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./backend/data.db")
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-me",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    # Allow both localhost and 127.0.0.1 by default in dev
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")  # 'text' or 'json'
    LOG_FILE_PATH: str | None = os.getenv("LOG_FILE_PATH", None)
    LOG_ROTATION_SIZE: int = int(os.getenv("LOG_ROTATION_SIZE", str(10 * 1024 * 1024)))  # 10MB default
    LOG_ROTATION_COUNT: int = int(os.getenv("LOG_ROTATION_COUNT", "5"))

    # Legacy logging settings (for backward compatibility)
    AGENT_LOG_LEVEL: str = os.getenv("AGENT_LOG_LEVEL", "INFO")
    LLM_DEBUG: bool = os.getenv("LLM_DEBUG", "false").lower() in ("true", "1", "yes")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
