from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.db import get_db
from ..models.entities import User
from ..models.schemas import Token, UserRead
from ..security.auth import create_access_token, verify_password, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


@router.post(
    "/token",
    response_model=Token,
    summary="Obtain JWT token",
    description="Authenticate using username and password to receive an access token.",
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """Issue a JWT token on successful authentication.

    Parameters:
    - username: form field
    - password: form field

    Returns:
    - Token: access_token and token_type
    """
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Retrieve the authenticated user's profile.",
)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user."""
    return UserRead.model_validate(current_user.__dict__)
