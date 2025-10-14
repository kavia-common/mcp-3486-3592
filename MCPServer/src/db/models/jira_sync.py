from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..session import Base

if TYPE_CHECKING:
    from .message import Message  # type: ignore  # for type hints only


class JiraSyncStatus(str, enum.Enum):
    """Allowed Jira sync statuses per schema."""
    pending = "pending"
    synced = "synced"
    error = "error"


class JiraSync(Base):
    """Tracks synchronization status between a Message and a JIRA issue."""

    __tablename__ = "JiraSync"
    __table_args__ = (
        Index("idx_jirasync_status", "sync_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    jira_issue_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # FK to Message.id
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('Message.id', ondelete=None, onupdate=None),
        nullable=True,
    )

    sync_status: Mapped[JiraSyncStatus] = mapped_column(
        Enum(JiraSyncStatus, name="jira_sync_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )

    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    # Relationship to Message
    message: Mapped[Optional["Message"]] = relationship(
        "Message",
        back_populates="jira_syncs",
        primaryjoin="JiraSync.message_id==Message.id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"JiraSync(id={self.id}, jira_issue_id={self.jira_issue_id!r}, status={self.sync_status})"
