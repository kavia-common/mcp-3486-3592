import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import get_db
from ..models.entities import Message
from ..models.schemas import MessageCreate, MessageRead, MessageUpdate
from ..security.auth import require_roles, get_current_user
from ..services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageRead, summary="Create message")
async def create_message(payload: MessageCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Create a new message with pending status."""
    svc = MessageService(db)
    msg = await svc.create_message(payload.content)
    await db.commit()
    await db.refresh(msg)
    return MessageRead.model_validate(msg.__dict__)


@router.get("/", response_model=List[MessageRead], summary="List messages")
async def list_messages(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """List all messages."""
    res = await db.execute(select(Message).order_by(Message.created_at.desc()))
    items = res.scalars().all()
    return [MessageRead.model_validate(i.__dict__) for i in items]


@router.get("/{message_id}", response_model=MessageRead, summary="Get message by ID")
async def get_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    res = await db.execute(select(Message).where(Message.id == message_id))
    msg = res.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageRead.model_validate(msg.__dict__)


@router.patch("/{message_id}", response_model=MessageRead, summary="Update message", description="Update status or JIRA link.")
async def update_message(message_id: uuid.UUID, payload: MessageUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    res = await db.execute(select(Message).where(Message.id == message_id))
    msg = res.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if payload.status is not None:
        msg.status = payload.status
    if payload.jira_issue_id is not None:
        msg.jira_issue_id = payload.jira_issue_id
    await db.commit()
    await db.refresh(msg)
    return MessageRead.model_validate(msg.__dict__)


@router.delete("/{message_id}", summary="Delete message", status_code=204)
async def delete_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    await db.execute(delete(Message).where(Message.id == message_id))
    await db.commit()
    return None


@router.post("/{message_id}/process", response_model=MessageRead, summary="Process message", description="Run rule engine on a message.")
async def process_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    svc = MessageService(db)
    msg = await svc.process_message(message_id)
    await db.commit()
    await db.refresh(msg)
    return MessageRead.model_validate(msg.__dict__)
