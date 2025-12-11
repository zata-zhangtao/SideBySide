from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db import init_db
from .routers import auth, users, wordlists, sessions, leaderboard, reports


def create_app() -> FastAPI:
    app = FastAPI(title="SideBySide API", version="0.1.0")

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

    # Initialize DB (create tables if needed)
    init_db()

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

