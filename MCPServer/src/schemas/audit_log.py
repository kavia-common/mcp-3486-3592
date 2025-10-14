from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class AuditLogQuery(BaseModel):
    """Query parameters for searching audit logs."""

    action: Optional[str] = Field(None, description="Filter by action name (exact or partial per endpoint behavior)")
    performed_by: Optional[UUID] = Field(None, description="Filter by performer user id")
    start_time: Optional[datetime] = Field(None, description="Filter logs from this timestamp (inclusive)")
    end_time: Optional[datetime] = Field(None, description="Filter logs up to this timestamp (inclusive)")
    limit: Optional[int] = Field(50, description="Max number of records to return")
    offset: Optional[int] = Field(0, description="Number of records to skip")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class AuditLogOut(BaseModel):
    """Response model representing an audit log entry."""

    id: UUID = Field(..., description="Audit log unique identifier")
    action: str = Field(..., description="Performed action name")
    performed_by: Optional[UUID] = Field(None, description="User id who performed the action (nullable for system actions)")
    timestamp: datetime = Field(..., description="When the action was performed")
    details: Optional[str] = Field(None, description="Additional information about the action")

    model_config = {
        "from_attributes": True,
    }
