from typing import Generator, Optional

from sqlalchemy.orm import Session

from ..core.security import decode_token
from ..db.session import get_db as _get_db
from ..db.models import User

# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy DB session and ensure it's closed after usage."""
    yield from _get_db()

# PUBLIC_INTERFACE
def get_current_user(optional: bool = False):
    """FastAPI dependency to get the current user from a Bearer token.

    Uses JWT bearer token to identify the user and loads from the database.
    If optional=True and no token is provided, returns None.
    """
    from fastapi import Depends, HTTPException, status
    from fastapi.security import OAuth2PasswordBearer

    # OAuth2 password flow token endpoint
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=not optional)

    async def _resolver(
        token: Optional[str] = Depends(oauth2_scheme),
        db: Session = Depends(get_db),
    ):
        if optional and not token:
            return None
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            payload = decode_token(token)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Subject contains user id
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

        # Load user from database
        user: Optional[User] = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return user

    return _resolver


# PUBLIC_INTERFACE
def require_admin():
    """Dependency that ensures the current user has admin role."""
    from fastapi import Depends, HTTPException, status

    async def _resolver(current_user: User = Depends(get_current_user())) -> User:
        if current_user.role.lower() != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
        return current_user

    return _resolver
