import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "User"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="performed_by_user")


class Message(Base):
    __tablename__ = "Message"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    jira_issue_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    jira_syncs: Mapped[list["JiraSync"]] = relationship(back_populates="message")

    __table_args__ = (
        CheckConstraint("status in ('pending','processed','failed')", name="ck_message_status"),
        Index("idx_message_status", "status"),
    )


class Rule(Base):
    __tablename__ = "Rule"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("User.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    performed_by_user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")

    __table_args__ = (Index("idx_auditlog_performed_by", "performed_by"),)


class JiraSync(Base):
    __tablename__ = "JiraSync"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jira_issue_id: Mapped[str] = mapped_column(String(255), nullable=False)
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("Message.id"), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    message: Mapped[Optional[Message]] = relationship(back_populates="jira_syncs")

    __table_args__ = (
        CheckConstraint("sync_status in ('pending','synced','error')", name="ck_jirasync_status"),
        Index("idx_jirasync_status", "sync_status"),
    )
