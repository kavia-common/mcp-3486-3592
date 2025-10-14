from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..db.models import JiraSync, JiraSyncStatus, Message
from ..utils.audit import audit_log
from .jira_client import JiraClient, JiraClientError

logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
async def ensure_issue_for_message(
    db: Session,
    message_id: UUID,
    *,
    project_key: Optional[str] = None,
    issue_type: str = "Task",
) -> Optional[str]:
    """Ensure a Jira issue exists for the given message.

    - If Message.jira_issue_id exists, verifies the issue exists (best effort) and returns it.
    - If not, attempts to create a Jira issue (summary from message content beginning) and persists linkage.
    - Creates/updates a JiraSync row with appropriate status.

    Returns:
    - jira_issue_id (key), or None if creation/verification fails.
    """
    settings = get_settings()
    project_key = project_key or settings.JIRA_PROJECT_KEY

    msg: Optional[Message] = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        logger.error("Message not found for id=%s; cannot ensure Jira issue.", message_id)
        return None

    existing_issue = msg.jira_issue_id

    # Create client (no async context manager support on JiraClient)
    client = JiraClient()

    try:
        if existing_issue:
            # Attempt to confirm issue exists
            try:
                await client.get_issue(existing_issue)
                _link_sync_record(db, message_id, existing_issue, JiraSyncStatus.synced)
                db.commit()
                return existing_issue
            except JiraClientError as e:
                logger.warning(
                    "Linked Jira issue not found/accessible for message=%s issue=%s: %s",
                    message_id,
                    existing_issue,
                    e,
                )

        # Create new issue only if project_key is available
        if not project_key:
            logger.error("No JIRA_PROJECT_KEY configured and message has no jira_issue_id; cannot create issue.")
            _link_sync_record(db, message_id, existing_issue or "unknown", JiraSyncStatus.error)
            db.commit()
            return None

        summary = _make_summary_from_content(msg.content)
        description = f"Auto-created by MCP Server for message {message_id}"
        created = await client.create_issue(
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
        )
        issue_key = created.get("key") or created.get("id")
        if not issue_key:
            logger.error("Jira did not return key/id for created issue. Payload=%s", created)
            _link_sync_record(db, message_id, "unknown", JiraSyncStatus.error)
            db.commit()
            return None

        # Persist link on message and create sync record
        msg.jira_issue_id = issue_key
        msg.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(msg)
        _link_sync_record(db, message_id, issue_key, JiraSyncStatus.synced)
        audit_log(
            db,
            "jira.issue.create",
            performed_by=None,
            details=f"Created Jira issue {issue_key} for message {message_id}",
        )
        db.commit()
        return issue_key

    except JiraClientError as e:
        logger.exception("Failed to ensure/create Jira issue for message=%s: %s", message_id, e)
        _link_sync_record(db, message_id, existing_issue or "unknown", JiraSyncStatus.error)
        db.commit()
        return None
    finally:
        try:
            await client.aclose()
        except Exception:  # pragma: no cover - defensive
            pass


# PUBLIC_INTERFACE
async def add_comment_for_message(db: Session, message_id: UUID, comment: str) -> bool:
    """Add a comment to the Jira issue linked to the message. Creates the issue if needed."""
    msg: Optional[Message] = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        logger.error("Message not found for id=%s; cannot add comment.", message_id)
        return False

    issue_key = msg.jira_issue_id
    if not issue_key:
        issue_key = await ensure_issue_for_message(db, message_id)
        if not issue_key:
            return False

    client = JiraClient()
    try:
        await client.add_comment(issue_key, comment)
        _link_sync_record(db, message_id, issue_key, JiraSyncStatus.synced)
        audit_log(db, "jira.comment.add", performed_by=None, details=f"Added comment to {issue_key} for message {message_id}")
        db.commit()
        return True
    except JiraClientError as e:
        logger.exception("Failed to add comment to Jira issue=%s for message=%s: %s", issue_key, message_id, e)
        _link_sync_record(db, message_id, issue_key, JiraSyncStatus.error)
        db.commit()
        return False
    finally:
        try:
            await client.aclose()
        except Exception:  # pragma: no cover
            pass


# PUBLIC_INTERFACE
def record_sync_status(db: Session, jira_issue_id: str, message_id: Optional[UUID], status: JiraSyncStatus, *, details: Optional[str] = None) -> JiraSync:
    """Record a JiraSync status transition and optional audit log. Synchronous helper for internal flows."""
    sync = _link_sync_record(db, message_id, jira_issue_id, status)
    if details:
        audit_log(db, "jira.sync.status", performed_by=None, details=f"[{status.value}] {jira_issue_id} message={message_id} :: {details}")
    db.commit()
    return sync


def _link_sync_record(db: Session, message_id: Optional[UUID], jira_issue_id: str, status: JiraSyncStatus) -> JiraSync:
    """Create or update a JiraSync record for the given jira_issue_id + message link."""
    sync: Optional[JiraSync] = (
        db.query(JiraSync)
        .filter(JiraSync.jira_issue_id == jira_issue_id)
        .filter(JiraSync.message_id == message_id)
        .first()
    )

    now = datetime.utcnow()
    if not sync:
        sync = JiraSync(
            jira_issue_id=jira_issue_id,
            message_id=message_id,
            sync_status=status,
            last_synced_at=now if status == JiraSyncStatus.synced else None,
        )
        db.add(sync)
    else:
        sync.sync_status = status
        if status == JiraSyncStatus.synced:
            sync.last_synced_at = now

    # Flush but do not commit here; caller may control transaction boundaries.
    db.flush()
    return sync


def _make_summary_from_content(content: str, max_len: int = 120) -> str:
    content = (content or "").strip().replace("\n", " ").replace("\r", " ")
    if len(content) <= max_len:
        return content if content else "Auto-created issue"
    return content[: max_len - 3] + "..."
