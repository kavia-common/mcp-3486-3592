from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MessageStatusEnum(str, enum.Enum):
    """Message processing status values consistent with ORM and DB."""
    pending = "pending"
    processed = "processed"
    failed = "failed"


# PUBLIC_INTERFACE
class MessageCreate(BaseModel):
    """Request payload to create a message for processing."""

    content: str = Field(..., description="Message content to process")
    status: MessageStatusEnum = Field(..., description="Initial message status")
    jira_issue_id: Optional[str] = Field(None, description="Optional JIRA issue id linked to the message")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class MessageUpdate(BaseModel):
    """Request payload to update a message."""

    content: Optional[str] = Field(None, description="Updated message content")
    status: Optional[MessageStatusEnum] = Field(None, description="Updated processing status")
    jira_issue_id: Optional[str] = Field(None, description="Updated JIRA issue id")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class MessageOut(BaseModel):
    """Response model representing a message."""

    id: UUID = Field(..., description="Message unique identifier")
    content: str = Field(..., description="Message content")
    status: MessageStatusEnum = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    jira_issue_id: Optional[str] = Field(None, description="Linked JIRA issue id, if any")

    model_config = {
        "from_attributes": True,
    }
