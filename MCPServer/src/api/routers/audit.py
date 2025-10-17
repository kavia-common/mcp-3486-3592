from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import get_db
from ..models.entities import AuditLog
from ..models.schemas import AuditRead
from ..security.auth import require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/", response_model=List[AuditRead], summary="List audit logs")
async def list_audit_logs(db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    res = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()))
    items = res.scalars().all()
    return [AuditRead.model_validate(i.__dict__) for i in items]
