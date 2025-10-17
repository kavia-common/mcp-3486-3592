from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from ..core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for ORM models."""
    pass


_settings = get_settings()
engine = create_async_engine(_settings.database_dsn(), echo=False, future=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)


# PUBLIC_INTERFACE
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
