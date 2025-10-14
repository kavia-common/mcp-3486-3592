from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..session import Base

if TYPE_CHECKING:
    from .audit_log import AuditLog  # type: ignore  # for type hints only


class User(Base):
    """User accounts for authentication and authorization."""

    __tablename__ = "User"

    # UUID primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Fields
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False)

    # Relationships
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="performed_by_user",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - convenience
        return f"User(id={self.id}, username={self.username!r}, role={self.role!r})"
