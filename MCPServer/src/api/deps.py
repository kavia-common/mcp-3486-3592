from typing import Generator, Optional

from sqlalchemy.orm import Session

from ..core.security import decode_token
from ..db.session import get_db as _get_db

# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy DB session and ensure it's closed after usage."""
    yield from _get_db()

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
