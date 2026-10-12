"""
Database engine and session factory.

Provides a SQLAlchemy engine, sessionmaker, and a get_session dependency
injection function used by route handlers. The engine is created once
and reused across requests.

All models import from here to get the Base class. The engine URL is
read from app.config.settings.database_url. In development this defaults
to SQLite; in production it should point to PostgreSQL.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def get_session() -> Generator:
    """
    Dependency injection for database sessions.

    Yields a new session for each request and ensures it is closed
    after the response is sent, even if an error occurred.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
