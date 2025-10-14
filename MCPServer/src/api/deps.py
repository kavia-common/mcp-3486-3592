from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from ..core.config import get_settings
from ..core.security import decode_token

# Create SQLAlchemy engine and session maker at module import.
# In future, for async support use async engine and async sessions.
_settings = get_settings()
_engine = create_engine(_settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy DB session and ensure it's closed after usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# PUBLIC_INTERFACE
def get_current_user(optional: bool = False):
    """FastAPI dependency to get the current user from a Bearer token.

    This is a placeholder; actual user retrieval from DB will be added later.
    """
    from fastapi import Depends, HTTPException, status
    from fastapi.security import OAuth2PasswordBearer

    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=not optional)

    async def _resolver(token: Optional[str] = Depends(oauth2_scheme)):
        if optional and not token:
            return None
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            payload = decode_token(token)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        # Placeholder: return payload now; integrate with DB user model later.
        return payload

    return _resolver
