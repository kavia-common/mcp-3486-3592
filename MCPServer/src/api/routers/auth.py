from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ...core.security import verify_password, create_access_token
from ...db.models import User
from ...schemas import Token, LoginRequest, UserOut
from ..deps import get_db, get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["auth"])


# PUBLIC_INTERFACE
@router.post(
    "/login",
    response_model=Token,
    summary="User login",
    description="Authenticate with username and password and receive a bearer JWT access token.",
    responses={
        200: {"description": "Login successful, returns JWT access token."},
        400: {"description": "Invalid request payload."},
        401: {"description": "Invalid username or password."},
    },
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
) -> Token:
    """
    Authenticate a user using username and password.

    Parameters:
    - credentials: LoginRequest with username and password.
    - db: SQLAlchemy Session dependency.

    Returns:
    - Token: access_token and token_type ("bearer").

    Raises:
    - 401 Unauthorized if the credentials are invalid.
    """
    # Find user by username
    user: Optional[User] = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Create JWT token with subject = user.id and include username and role as claims
    token = create_access_token(
        subject=str(user.id),
        additional_claims={"username": user.username, "role": user.role},
    )
    return Token(access_token=token, token_type="bearer")


# PUBLIC_INTERFACE
@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 password flow login",
    description="Standard OAuth2 token endpoint that accepts form data (username and password).",
)
def oauth2_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """
    OAuth2-compatible token endpoint.

    Accepts:
    - form_data: OAuth2PasswordRequestForm (username, password).

    Returns:
    - Token: Bearer token.
    """
    user: Optional[User] = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(
        subject=str(user.id),
        additional_claims={"username": user.username, "role": user.role},
    )
    return Token(access_token=token, token_type="bearer")


# PUBLIC_INTERFACE
@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current user",
    description="Return the currently authenticated user details.",
    responses={
        200: {"description": "Current user returned."},
        401: {"description": "Not authenticated."},
    },
)
def read_me(current_user: User = Depends(get_current_user())) -> UserOut:
    """
    Get current authenticated user.

    Parameters:
    - current_user: Injected by get_current_user dependency.

    Returns:
    - UserOut: Safe user representation.
    """
    return UserOut.model_validate(current_user)
