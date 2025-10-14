from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JiraSyncStatusEnum(str, enum.Enum):
    """Jira sync status values consistent with ORM and DB."""
    pending = "pending"
    synced = "synced"
    error = "error"


# PUBLIC_INTERFACE
class JiraSyncCreate(BaseModel):
    """Request payload to create a Jira sync linkage."""

    jira_issue_id: str = Field(..., description="JIRA issue identifier")
    message_id: UUID = Field(..., description="Linked message identifier")
    sync_status: JiraSyncStatusEnum = Field(..., description="Initial sync status")
    last_synced_at: Optional[datetime] = Field(None, description="Timestamp when last successfully synced")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class JiraSyncOut(BaseModel):
    """Response model representing a Jira sync record."""

    id: UUID = Field(..., description="Jira sync record unique identifier")
    jira_issue_id: str = Field(..., description="JIRA issue identifier")
    message_id: Optional[UUID] = Field(None, description="Linked message identifier (nullable in DB)")
    sync_status: JiraSyncStatusEnum = Field(..., description="Sync status")
    last_synced_at: Optional[datetime] = Field(None, description="Last sync timestamp")

    model_config = {
        "from_attributes": True,
    }
