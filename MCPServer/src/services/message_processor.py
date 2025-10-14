from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from ..db.models import Message, MessageStatus, Rule
from ..utils.errors import is_transient_error
from .jira_sync_service import ensure_issue_for_message, record_sync_status
from ..db.models import JiraSyncStatus

logger = logging.getLogger(__name__)


def _load_active_rules(db: Session) -> List[Rule]:
    """Load active rules from DB, ordered by created_at ascending for deterministic application."""
    return db.query(Rule).filter(Rule.is_active == True).order_by(Rule.created_at.asc()).all()  # noqa: E712


# PUBLIC_INTERFACE
def apply_rules(db: Session, message: Message) -> Message:
    """Apply active rules to the message content.

    This is a placeholder rule engine. For now, it:
    - Loads active rules.
    - For each rule, if rule.definition is a simple 'prefix: <text>' pattern, it prefixes the message.
      Otherwise, it no-ops. This demonstrates extensibility for future scripting.

    Returns the mutated message object (not committed).
    """
    rules = _load_active_rules(db)
    content = message.content
    for r in rules:
        definition = (r.definition or "").strip()
        if definition.lower().startswith("prefix:"):
            prefix = definition[len("prefix:") :].strip()
            if prefix:
                content = f"{prefix} {content}"
    if content != message.content:
        message.content = content
        message.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return message


# PUBLIC_INTERFACE
async def process_message(db: Session, message: Message) -> bool:
    """Process a single message using apply_rules and optional Jira integration.

    Steps:
    - Apply rules (mutating content when applicable).
    - If message has a jira_issue_id, best-effort ensure the issue exists and mark sync status.
      If no id, no-op; future steps may create issues based on advanced rules.
    - On success set status='processed'; on failure set status='failed'.

    Returns True on success, False on failure.
    """
    try:
        # Apply rules
        apply_rules(db, message)

        # Optional JIRA ensure if linked
        if message.jira_issue_id:
            try:
                # ensure_issue_for_message may update message link or sync table
                issue_key = await ensure_issue_for_message(db, message.id)
                if issue_key:
                    record_sync_status(db, issue_key, message.id, JiraSyncStatus.synced, details="message processing ensure ok")
                else:
                    # do not fail message solely on inability to ensure Jira; record error
                    record_sync_status(db, message.jira_issue_id, message.id, JiraSyncStatus.error, details="ensure failed during message processing")
            except Exception as je:
                # if transient, let caller retry via outer retry; else record error and continue
                if is_transient_error(je):
                    raise
                logger.exception("Non-transient Jira error during message processing id=%s: %s", message.id, je)
                record_sync_status(db, message.jira_issue_id, message.id, JiraSyncStatus.error, details="non-transient jira error")

        # Mark processed
        message.status = MessageStatus.processed
        message.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(message)
        return True
    except Exception as e:
        logger.exception("Error processing message id=%s: %s", message.id, e)
        # Status update will be handled by caller on final failure
        return False
