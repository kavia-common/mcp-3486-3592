from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..session import Base

if TYPE_CHECKING:
    from .jira_sync import JiraSync  # type: ignore  # for type hints only


class MessageStatus(str, enum.Enum):
    """Allowed message processing states per schema."""
    pending = "pending"
    processed = "processed"
    failed = "failed"


class Message(Base):
    """Stored messages for processing and JIRA linkage."""

    __tablename__ = "Message"
    __table_args__ = (
        Index("idx_message_status", "status"),
    )

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Content and status
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    # Optional JIRA issue id stored on message for convenience
    jira_issue_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    jira_syncs: Mapped[list["JiraSync"]] = relationship(
        "JiraSync",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Message(id={self.id}, status={self.status}, jira_issue_id={self.jira_issue_id!r})"
