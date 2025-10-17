from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Message, AuditLog, JiraSync
from .rule_engine import RuleEngine


class MessageService:
    """Service for message lifecycle operations."""

    def __init__(self, db: AsyncSession, rule_engine: Optional[RuleEngine] = None):
        self.db = db
        self.rule_engine = rule_engine or RuleEngine()

    # PUBLIC_INTERFACE
    async def create_message(self, content: str) -> Message:
        """Create a pending message and write audit log."""
        msg = Message(content=content, status="pending")
        self.db.add(msg)
        await self.db.flush()
        await self._audit("message.create", details=f"Message {msg.id} created")
        return msg

    # PUBLIC_INTERFACE
    async def process_message(self, message_id: uuid.UUID) -> Message:
        """Process a message via rule engine, set status accordingly, and audit."""
        result = await self.db.execute(select(Message).where(Message.id == message_id))
        msg = result.scalar_one()
        try:
            await self.rule_engine.apply_rules(self.db, msg)
            msg.status = "processed"
            msg.updated_at = datetime.utcnow()
            await self._audit("message.process", details=f"Message {msg.id} processed")
        except Exception as exc:  # noqa: BLE001
            msg.status = "failed"
            msg.updated_at = datetime.utcnow()
            await self._audit("message.process.error", details=f"Message {msg.id} failed: {exc}")
        await self.db.flush()
        return msg

    # PUBLIC_INTERFACE
    async def link_jira(self, message_id: uuid.UUID, jira_issue_id: str) -> JiraSync:
        """Link a message to a JIRA issue via JiraSync."""
        result = await self.db.execute(select(Message).where(Message.id == message_id))
        msg = result.scalar_one()
        msg.jira_issue_id = jira_issue_id
        sync = JiraSync(jira_issue_id=jira_issue_id, message_id=msg.id, sync_status="pending")
        self.db.add(sync)
        await self.db.flush()
        await self._audit("jira.link", details=f"Linked message {msg.id} to {jira_issue_id}")
        return sync

    async def _audit(self, action: str, details: Optional[str] = None, performed_by: Optional[uuid.UUID] = None) -> None:
        log = AuditLog(action=action, details=details, performed_by=performed_by)
        self.db.add(log)
        await self.db.flush()
