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
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

