from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ...db.models import Message, MessageStatus, JiraSync
from ...schemas import MessageCreate, MessageUpdate, MessageOut, MessageStatusEnum
from ..deps import get_db, get_current_user
from ...utils.audit import audit_log
from ...services.message_processing import enqueue_message_processing

router = APIRouter(prefix="/messages", tags=["messages"])


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a message",
    description="Create a new message with initial status (typically 'pending'). Also records an audit log.",
    responses={
        201: {"description": "Message created successfully."},
        400: {"description": "Invalid status or payload."},
        401: {"description": "Not authenticated."},
    },
)
def create_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user()),
) -> MessageOut:
    """
    Create a new message record.

    Parameters:
    - payload: MessageCreate with content, status, and optional jira_issue_id.

    Returns:
    - MessageOut: The created message.
    """
    try:
        # Validate status enum matches DB enum; coercion via name matching
        status_val = MessageStatus(payload.status.value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")

    msg = Message(
        content=payload.content,
        status=status_val,
        jira_issue_id=payload.jira_issue_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    audit_log(
        db=db,
        action="message.create",
        performed_by=current_user.id if current_user else None,
        details=f"Created message {msg.id} status={msg.status}",
    )
    db.commit()  # persist audit log
    return MessageOut.model_validate(msg)


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[MessageOut],
    summary="List messages",
    description=(
        "Retrieve messages with optional filters: status, created date range, jira_issue_id. "
        "Supports pagination via limit/offset."
    ),
    responses={
        200: {"description": "List of messages returned."},
        401: {"description": "Not authenticated."},
    },
)
def list_messages(
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user()),  # authentication required
    status_filter: Optional[MessageStatusEnum] = Query(
        None, alias="status", description="Filter by message status"
    ),
    start_date: Optional[datetime] = Query(
        None, description="Filter by created_at >= start_date (ISO timestamp)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter by created_at <= end_date (ISO timestamp)"
    ),
    jira_issue_id: Optional[str] = Query(None, description="Filter by linked JIRA issue id"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip before returning"),
) -> List[MessageOut]:
    """
    List messages with filters and pagination.
    """
    q = db.query(Message)

    conditions = []
    if status_filter is not None:
        try:
            conditions.append(Message.status == MessageStatus(status_filter.value))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter")
    if start_date is not None:
        conditions.append(Message.created_at >= start_date)
    if end_date is not None:
        conditions.append(Message.created_at <= end_date)
    if jira_issue_id is not None:
        conditions.append(Message.jira_issue_id == jira_issue_id)

    if conditions:
        q = q.filter(and_(*conditions))

    # Index on status will be used when filtering by status
    items = q.order_by(Message.created_at.desc()).offset(offset).limit(limit).all()
    return [MessageOut.model_validate(i) for i in items]


# PUBLIC_INTERFACE
@router.get(
    "/{message_id}",
    response_model=MessageOut,
    summary="Get message by ID",
    description="Retrieve a message by its UUID.",
    responses={
        200: {"description": "Message returned."},
        401: {"description": "Not authenticated."},
        404: {"description": "Message not found."},
    },
)
def get_message_by_id(
    message_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user()),
) -> MessageOut:
    """
    Get a single message by ID.
    """
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return MessageOut.model_validate(msg)


# PUBLIC_INTERFACE
@router.patch(
    "/{message_id}",
    response_model=MessageOut,
    summary="Update message",
    description="Update message content, status, or linked JIRA issue id. Records an audit log.",
    responses={
        200: {"description": "Message updated."},
        400: {"description": "Invalid status or no changes."},
        401: {"description": "Not authenticated."},
        404: {"description": "Message not found."},
    },
)
def update_message(
    message_id: UUID,
    payload: MessageUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user()),
) -> MessageOut:
    """
    Update an existing message.
    """
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    changes: list[str] = []

    if payload.content is not None and payload.content != msg.content:
        msg.content = payload.content
        changes.append("content")

    if payload.status is not None and payload.status.value != msg.status.value:
        try:
            msg.status = MessageStatus(payload.status.value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        changes.append(f"status={msg.status.value}")

    if payload.jira_issue_id is not None and payload.jira_issue_id != msg.jira_issue_id:
        msg.jira_issue_id = payload.jira_issue_id
        changes.append(f"jira_issue_id={msg.jira_issue_id}")

    if not changes:
        # No meaningful change; return current message
        return MessageOut.model_validate(msg)

    # update timestamp if any change
    msg.updated_at = datetime.utcnow()

    db.add(msg)
    db.commit()
    db.refresh(msg)

    audit_log(
        db=db,
        action="message.update",
        performed_by=current_user.id if current_user else None,
        details=f"Updated message {msg.id}: " + ", ".join(changes),
    )
    db.commit()
    return MessageOut.model_validate(msg)


# PUBLIC_INTERFACE
@router.post(
    "/{message_id}/process",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger message processing",
    description=(
        "Enqueue the message for processing via a background task stub. "
        "Does not block; returns 202 Accepted on successful enqueue."
    ),
    responses={
        202: {"description": "Processing enqueued."},
        401: {"description": "Not authenticated."},
        404: {"description": "Message not found."},
    },
)
def trigger_processing(
    message_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user()),
) -> dict:
    """
    Trigger processing for a message by enqueuing a background task.

    Returns:
    - JSON with accepted=true.
    """
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # Optional: ensure message exists in JiraSync linkage if jira_issue_id present
    # Not required, but we may use it for optimization
    if msg.jira_issue_id:
        # lightweight existence check; does not change behavior if missing
        _ = db.query(JiraSync).filter(JiraSync.jira_issue_id == msg.jira_issue_id).first()

    # Audit before enqueue
    audit_log(
        db=db,
        action="message.process.enqueue",
        performed_by=current_user.id if current_user else None,
        details=f"Enqueue processing for message {msg.id}",
    )
    db.commit()

    # Enqueue background processing task (stubbed service)
    background_tasks.add_task(enqueue_message_processing, str(message_id))

    return {"accepted": True, "message_id": str(message_id)}
