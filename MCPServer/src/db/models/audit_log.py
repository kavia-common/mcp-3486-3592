from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..session import Base

if TYPE_CHECKING:
    from .user import User  # type: ignore  # for type hints only


class AuditLog(Base):
    """Audit log entry capturing user actions and details."""

    __tablename__ = "AuditLog"
    __table_args__ = (
        Index("idx_auditlog_performed_by", "performed_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    action: Mapped[str] = mapped_column(String(255), nullable=False)

    # FK to User.id
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('User.id', ondelete=None, onupdate=None),
        nullable=True,  # DB allows null? Schema shows just references; keep nullable to allow system actions without user.
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False)

    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship to User
    performed_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        primaryjoin="AuditLog.performed_by==User.id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"AuditLog(id={self.id}, action={self.action!r}, performed_by={self.performed_by})"
