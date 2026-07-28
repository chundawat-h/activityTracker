"""
SQLAlchemy engine and session management.

Fully database-independent: SQLite is used by default for local development,
but switching to Postgres in production only requires changing DATABASE_URL
(e.g. postgresql+psycopg2://user:pass@host:5432/dbname). No code changes.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import settings


def _build_engine() -> Engine:
    connect_args = {}
    # SQLite needs this flag when accessed from multiple threads (scheduler +
    # potential future API server). Postgres/MySQL don't need or accept it.
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that yields a session and guarantees commit/rollback/close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Safe to call repeatedly (no-op if tables exist)."""
    from backend.database import models  # noqa: F401  (ensure models are registered)
    from backend.database.base import Base

    Base.metadata.create_all(bind=engine)
