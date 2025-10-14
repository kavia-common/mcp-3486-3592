from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query, Request, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...db.models import JiraSync, JiraSyncStatus, Message
from ...schemas import JiraSyncOut, JiraSyncStatusEnum
from ..deps import get_db, get_current_user
from ...utils.audit import audit_log
from ...services.jira_sync_service import ensure_issue_for_message, record_sync_status

router = APIRouter(prefix="/jira-sync", tags=["jira"])


# PUBLIC_INTERFACE
@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue JIRA sync",
    description=(
        "Queue a JIRA sync either by providing a message_id to ensure/create and sync "
        "its JIRA issue, or by providing an explicit jira_issue_id to record a pending sync entry."
    ),
    responses={
        202: {"description": "Sync accepted/enqueued."},
        400: {"description": "Invalid input."},
        401: {"description": "Not authenticated."},
        404: {"description": "Message not found."},
    },
)
async def queue_jira_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user()),
    message_id: Optional[UUID] = Query(
        None, description="Message ID to sync with JIRA (ensures issue exists/created)."
    ),
    jira_issue_id: Optional[str] = Query(
        None, description="Explicit JIRA issue key/id to mark as pending sync."
    ),
) -> dict:
    """
    Queue a JIRA sync request.

    Either message_id or jira_issue_id must be provided. If message_id is provided, the service will
    ensure a JIRA issue exists (creating if needed) and record sync status. If jira_issue_id is provided
    without a message, a JiraSync record is created/updated to pending for tracking.
    """
    if not message_id and not jira_issue_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide message_id or jira_issue_id")

    result: dict = {"accepted": True}

    if message_id:
        msg = db.query(Message).filter(Message.id == message_id).first()
        if not msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        audit_log(
            db=db,
            action="jira.sync.enqueue",
            performed_by=current_user.id if current_user else None,
            details=f"Queue sync for message {message_id}",
        )
        db.commit()

        async def _do_sync(mid: UUID):
            # Best-effort ensure issue and record status
            issue_key = await ensure_issue_for_message(db, mid)
            if issue_key:
                record_sync_status(db, issue_key, mid, JiraSyncStatus.synced, details="ensure_issue_for_message completed")
            else:
                record_sync_status(db, "unknown", mid, JiraSyncStatus.error, details="ensure_issue_for_message failed")

        # Using background_tasks to decouple from request lifecycle
        background_tasks.add_task(_do_sync, message_id)
        result["message_id"] = str(message_id)

    if jira_issue_id and not message_id:
        # Record a pending sync entry for tracking
        record_sync_status(db, jira_issue_id, None, JiraSyncStatus.pending, details="Pending sync queued (no message)")
        audit_log(
            db=db,
            action="jira.sync.enqueue",
            performed_by=current_user.id if current_user else None,
            details=f"Queue sync for jira_issue_id={jira_issue_id}",
        )
        db.commit()
        result["jira_issue_id"] = jira_issue_id

    return result


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[JiraSyncOut],
    summary="List JIRA syncs",
    description="List JIRA sync records with optional filters and pagination.",
    responses={
        200: {"description": "List of Jira sync records."},
        401: {"description": "Not authenticated."},
    },
)
def list_jira_syncs(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user()),
    status_filter: Optional[JiraSyncStatusEnum] = Query(
        None, alias="status", description="Filter by sync status"
    ),
    jira_issue_id: Optional[str] = Query(None, description="Filter by JIRA issue id/key"),
    message_id: Optional[UUID] = Query(None, description="Filter by message id"),
    start: Optional[datetime] = Query(None, description="Filter last_synced_at >= start (inclusive)"),
    end: Optional[datetime] = Query(None, description="Filter last_synced_at <= end (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip before returning"),
) -> List[JiraSyncOut]:
    """
    List jira sync records with filters and pagination.
    """
    q = db.query(JiraSync)
    conditions = []
    if status_filter is not None:
        try:
            conditions.append(JiraSync.sync_status == JiraSyncStatus(status_filter.value))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter")
    if jira_issue_id:
        conditions.append(JiraSync.jira_issue_id == jira_issue_id)
    if message_id:
        conditions.append(JiraSync.message_id == message_id)
    if start is not None:
        conditions.append(JiraSync.last_synced_at >= start)
    if end is not None:
        conditions.append(JiraSync.last_synced_at <= end)

    if conditions:
        q = q.filter(and_(*conditions))

    items = q.order_by(JiraSync.last_synced_at.desc().nullslast()).offset(offset).limit(limit).all()
    return [JiraSyncOut.model_validate(i) for i in items]


# PUBLIC_INTERFACE
@router.get(
    "/{sync_id}",
    response_model=JiraSyncOut,
    summary="Get JIRA sync by ID",
    description="Retrieve a single JIRA sync record by its UUID.",
    responses={
        200: {"description": "Jira sync record returned."},
        401: {"description": "Not authenticated."},
        404: {"description": "Sync record not found."},
    },
)
def get_jira_sync_by_id(
    sync_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user()),
) -> JiraSyncOut:
    """
    Get a JIRA sync record by ID.
    """
    sync = db.query(JiraSync).filter(JiraSync.id == sync_id).first()
    if not sync:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync record not found")
    return JiraSyncOut.model_validate(sync)


# PUBLIC_INTERFACE
@router.post(
    "/{sync_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a JIRA sync record",
    description="Retry the sync process for the given JIRA sync record ID.",
    responses={
        202: {"description": "Retry accepted."},
        401: {"description": "Not authenticated."},
        404: {"description": "Sync record not found."},
    },
)
async def retry_jira_sync(
    sync_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user()),
) -> dict:
    """
    Retry a sync record by re-running ensure/create issue logic if applicable.
    """
    sync = db.query(JiraSync).filter(JiraSync.id == sync_id).first()
    if not sync:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync record not found")

    audit_log(
        db=db,
        action="jira.sync.retry",
        performed_by=current_user.id if current_user else None,
        details=f"Retry sync for sync_id={sync_id} jira_issue_id={sync.jira_issue_id} message_id={sync.message_id}",
    )
    db.commit()

    async def _do_retry(s_id: UUID, jira_issue: str, msg_id: Optional[UUID]):
        if msg_id:
            issue_key = await ensure_issue_for_message(db, msg_id)
            if issue_key:
                record_sync_status(db, issue_key, msg_id, JiraSyncStatus.synced, details="retry ensure_issue_for_message completed")
            else:
                record_sync_status(db, jira_issue or "unknown", msg_id, JiraSyncStatus.error, details="retry ensure_issue_for_message failed")
        else:
            # No message associated; mark pending as a no-op retry (external handlers may process)
            record_sync_status(db, jira_issue, None, JiraSyncStatus.pending, details="retry queued (no message)")

    background_tasks.add_task(_do_retry, sync_id, sync.jira_issue_id, sync.message_id)

    return {"accepted": True, "sync_id": str(sync_id)}


# PUBLIC_INTERFACE
@router.post(
    "/jira/webhook",
    summary="JIRA webhook receiver",
    description=(
        "Optional endpoint to receive JIRA webhooks. Secured via shared secret in header 'X-JIRA-SECRET'. "
        "Updates sync status on events like comment added or issue updated."
    ),
    responses={
        200: {"description": "Webhook processed."},
        400: {"description": "Invalid or unauthorized webhook."},
    },
)
async def jira_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive a JIRA webhook and update sync records accordingly.

    Security:
    - Requires env var JIRA_WEBHOOK_SECRET to be set server-side.
    - Client must send header X-JIRA-SECRET with the shared value.

    Minimal behavior:
    - Extract issue id/key from the payload and mark corresponding JiraSync rows as 'synced'
      with last_synced_at set to now (best-effort).
    """
    settings = get_settings()
    secret = getattr(settings, "JIRA_WEBHOOK_SECRET", None)
    if not secret:
        # Webhook not enabled
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook not enabled")

    provided = request.headers.get("X-JIRA-SECRET")
    if not provided or provided != secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unauthorized webhook")

    body = await request.json()
    # Attempt to parse issue key from Jira webhook payloads
    # Common shape: {"issue": {"key": "ABC-123", "id": "10001"}, "webhookEvent": "...", ...}
    issue_key = None
    try:
        if isinstance(body, dict):
            issue = body.get("issue") or {}
            issue_key = issue.get("key") or issue.get("id")
    except Exception:
        issue_key = None

    if not issue_key:
        # Accept but unable to process
        return {"processed": False, "reason": "missing issue key"}

    # Update or create sync record to synced as a best-effort
    record_sync_status(db, str(issue_key), None, JiraSyncStatus.synced, details="webhook event received")
    audit_log(db, "jira.webhook", performed_by=None, details=f"Webhook for issue={issue_key}")
    db.commit()

    return {"processed": True, "issue": issue_key}
