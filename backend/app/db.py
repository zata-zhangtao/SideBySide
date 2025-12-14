from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.engine import Engine
from sqlalchemy import inspect, text

from .core.config import settings
from .core.logging import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

engine: Engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    future=True,
)


def _apply_minimal_migrations() -> None:
    """
    Best-effort, idempotent migrations to bring older local DBs up-to-date
    without dropping data. It checks for expected columns and adds missing ones.
    Works for SQLite and Postgres.
    """
    dialect = engine.dialect.name  # 'sqlite' | 'postgresql' | ...
    inspector = inspect(engine)
    logger.debug(f"Running database migrations for dialect: {dialect}")

    # Table -> { column: logical_type }
    expected: dict[str, dict[str, str]] = {
        "user": {
            "username": "text",
            "email": "text",
            "password_hash": "text",
        },
        "friendship": {
            "user_id": "int",
            "friend_id": "int",
        },
        "wordlist": {
            "owner_id": "int",
            "name": "text",
            "description": "text",
        },
        "word": {
            "list_id": "int",
            "term": "text",
            "definition": "text",
            "example": "text",
        },
        "studysession": {
            "wordlist_id": "int",
            "created_by": "int",
            "user_a_id": "int",
            "user_b_id": "int",
            "created_at": "datetime",
            "type": "text",
            "status": "text",
        },
        "attempt": {
            "session_id": "int",
            "user_id": "int",
            "word_id": "int",
            "answer_text": "text",
            "correct": "bool",
            "points": "int",
            "created_at": "datetime",
        },
    }

    type_map = {
        "sqlite": {"int": "INTEGER", "text": "TEXT", "bool": "BOOLEAN", "datetime": "DATETIME"},
        "postgresql": {"int": "INTEGER", "text": "TEXT", "bool": "BOOLEAN", "datetime": "TIMESTAMP"},
    }

    def q(ident: str) -> str:
        # Quote identifiers for safety (handles reserved names like user/type)
        return f'"{ident}"'

    existing_tables = set(inspector.get_table_names())
    logger.debug(f"Existing tables: {existing_tables}")

    columns_added = 0
    with engine.begin() as conn:
        for table, cols in expected.items():
            if table not in existing_tables:
                # If table didn't exist before, create_all() below will create it with full schema
                # Skip here; a second reflection would find it but no extra action is needed.
                logger.debug(f"Table '{table}' does not exist yet, will be created by create_all()")
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
            for col, ltype in cols.items():
                if col in existing_cols:
                    continue
                sql_type = type_map.get(dialect, type_map["sqlite"]).get(ltype, "TEXT")
                alter = f"ALTER TABLE {q(table)} ADD COLUMN {q(col)} {sql_type}"
                logger.info(f"Adding missing column: {table}.{col} ({sql_type})")
                conn.exec_driver_sql(alter)
                columns_added += 1

    if columns_added > 0:
        logger.info(f"Database migrations completed: {columns_added} columns added")
    else:
        logger.debug("Database migrations completed: no changes needed")


def init_db() -> None:
    """Initialize database: create tables and run migrations."""
    logger.info("Initializing database")
    try:
        # Create any missing tables first
        SQLModel.metadata.create_all(engine)
        logger.debug("Database tables created/verified")

        # Then add any missing columns on existing tables (non-destructive)
        _apply_minimal_migrations()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
