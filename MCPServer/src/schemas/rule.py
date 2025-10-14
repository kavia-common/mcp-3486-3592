from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class RuleCreate(BaseModel):
    """Request payload to create a rule."""

    name: str = Field(..., description="Rule name")
    definition: str = Field(..., description="Rule definition or script body")
    is_active: Optional[bool] = Field(True, description="Whether the rule is active")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class RuleUpdate(BaseModel):
    """Request payload to update a rule."""

    name: Optional[str] = Field(None, description="Updated rule name")
    definition: Optional[str] = Field(None, description="Updated rule definition")
    is_active: Optional[bool] = Field(None, description="Toggle active state")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class RuleOut(BaseModel):
    """Response model for a rule."""

    id: UUID = Field(..., description="Rule unique identifier")
    name: str = Field(..., description="Rule name")
    definition: str = Field(..., description="Rule definition or script")
    is_active: bool = Field(..., description="Whether the rule is active")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {
        "from_attributes": True,
    }
