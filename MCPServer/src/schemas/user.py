from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class UserCreate(BaseModel):
    """Request payload to create a new user."""

    username: str = Field(..., description="Unique username")
    password: str = Field(..., description="Plain text password to be hashed server-side")
    role: str = Field(..., description="Role of the user")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class UserUpdate(BaseModel):
    """Request payload to update an existing user."""

    password: Optional[str] = Field(None, description="New plain text password to be hashed")
    role: Optional[str] = Field(None, description="Updated role of the user")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class UserOut(BaseModel):
    """Response model for user data (excludes password hash)."""

    id: UUID = Field(..., description="User unique identifier")
    username: str = Field(..., description="Unique username")
    role: str = Field(..., description="Role of the user")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {
        "from_attributes": True,
    }
