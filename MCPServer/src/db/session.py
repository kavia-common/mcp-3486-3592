"""Database session and base model utilities for the MCP Server."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..core.config import get_settings

# Declarative base for all ORM models
Base = declarative_base()

# Engine and SessionLocal creation.
# Note: We keep sync engine/sessions. For async, migrate to create_async_engine and AsyncSession.
_settings = get_settings()
engine = create_engine(_settings.DATABASE_URL, pool_pre_ping=True)

# Configure sessionmaker
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy DB session and ensure it's closed after usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
