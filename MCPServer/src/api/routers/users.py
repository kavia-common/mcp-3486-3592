from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.security import hash_password
from ...db.models import User
from ...schemas import UserCreate, UserUpdate, UserOut
from ..deps import get_db, require_admin, get_current_user
from ...utils.audit import audit_log

router = APIRouter(prefix="/users", tags=["users"])


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=UserOut,
    summary="Create user (admin only)",
    description="Create a new user with a hashed password. Admin privileges required.",
    responses={
        201: {"description": "User created successfully."},
        400: {"description": "Username already exists."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
    },
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    current_user: User = Depends(get_current_user()),
) -> UserOut:
    """
    Create a new user.

    Parameters:
    - payload: UserCreate containing username, password, and role.
    - db: SQLAlchemy session.
    - _: Admin check via require_admin.
    - current_user: The admin performing the action (for audit).

    Returns:
    - UserOut: Created user details without password.
    """
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit_log(
        db=db,
        action="user.create",
        performed_by=current_user.id,
        details=f"Created user {user.username} ({user.id}) with role {user.role}",
    )
    return UserOut.model_validate(user)


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[UserOut],
    summary="List users (admin only)",
    description="List users with pagination support. Admin privileges required.",
    responses={
        200: {"description": "List of users returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
    },
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    limit: int = Query(50, ge=1, le=200, description="Max number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
) -> List[UserOut]:
    """
    List users with pagination.

    Parameters:
    - limit: Max number of users to return (default 50).
    - offset: Number of users to skip (default 0).

    Returns:
    - List[UserOut]: Users.
    """
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [UserOut.model_validate(u) for u in users]


# PUBLIC_INTERFACE
@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get user by ID (admin only)",
    description="Retrieve a single user by ID. Admin privileges required.",
    responses={
        200: {"description": "User returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
        404: {"description": "User not found."},
    },
)
def get_user_by_id(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
) -> UserOut:
    """
    Get user by ID.

    Parameters:
    - user_id: UUID of the user.

    Returns:
    - UserOut: The user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)


# PUBLIC_INTERFACE
@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Update user (admin only)",
    description="Update an existing user's password and/or role. Admin privileges required.",
    responses={
        200: {"description": "User updated."},
        400: {"description": "Invalid request."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
        404: {"description": "User not found."},
    },
)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    current_user: User = Depends(get_current_user()),
) -> UserOut:
    """
    Update a user.

    Parameters:
    - user_id: UUID of the user to update.
    - payload: Fields to update (password, role).

    Returns:
    - UserOut: Updated user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changes: list[str] = []
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changes.append("password")
    if payload.role is not None:
        user.role = payload.role
        changes.append(f"role={payload.role}")

    if not changes:
        # no-op update
        return UserOut.model_validate(user)

    db.add(user)
    db.commit()
    db.refresh(user)

    audit_log(
        db=db,
        action="user.update",
        performed_by=current_user.id,
        details=f"Updated user {user.username} ({user.id}): " + ", ".join(changes),
    )
    return UserOut.model_validate(user)


# PUBLIC_INTERFACE
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user (admin only)",
    description="Delete a user by ID. Admin privileges required.",
    responses={
        204: {"description": "User deleted."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
        404: {"description": "User not found."},
    },
)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    current_user: User = Depends(get_current_user()),
) -> None:
    """
    Delete a user.

    Parameters:
    - user_id: UUID of the user to delete.

    Returns:
    - No content on success.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    username = user.username
    uid = user.id
    db.delete(user)
    db.commit()

    audit_log(
        db=db,
        action="user.delete",
        performed_by=current_user.id,
        details=f"Deleted user {username} ({uid})",
    )
    return None
