from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..dependencies import get_jira_service
from ..models.db import get_db
from ..models.entities import Message, JiraSync
from ..models.schemas import JiraIssueLinkRequest, JiraSyncRead
from ..security.auth import require_roles
from ..services.jira_service import JiraService

router = APIRouter(prefix="/jira", tags=["jira"])


@router.post("/link", response_model=JiraSyncRead, summary="Link message to JIRA")
async def link_message_to_jira(
    payload: JiraIssueLinkRequest,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
):
    res = await db.execute(select(Message).where(Message.id == payload.message_id))
    msg = res.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    sync = JiraSync(jira_issue_id=payload.jira_issue_id, message_id=msg.id, sync_status="pending")
    db.add(sync)
    msg.jira_issue_id = payload.jira_issue_id
    await db.commit()
    await db.refresh(sync)
    return JiraSyncRead.model_validate(sync.__dict__)


@router.get("/issue/{issue_id}", summary="Get JIRA issue")
async def get_issue(issue_id: str, jira: JiraService = Depends(get_jira_service), _: Any = Depends(require_roles("admin"))):
    data: Dict[str, Any] = await jira.get_issue(issue_id)
    return data
