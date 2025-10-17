from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import get_db
from ..models.entities import User
from ..models.schemas import UserCreate, UserRead
from ..security.auth import get_password_hash, require_roles

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserRead, summary="Create user", description="Create a new user (admin only).")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_roles("admin"))):
    """Create a user with hashed password and specified role."""
    exists = await db.execute(select(User).where(User.username == payload.username))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=payload.username, password_hash=get_password_hash(payload.password), role=payload.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user.__dict__)


@router.get("/", response_model=List[UserRead], summary="List users", description="List all users (admin only).")
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_roles("admin"))):
    """List all users."""
    res = await db.execute(select(User))
    users = res.scalars().all()
    return [UserRead.model_validate(u.__dict__) for u in users]
