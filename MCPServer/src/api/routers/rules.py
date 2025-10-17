import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import get_db
from ..models.entities import Rule
from ..models.schemas import RuleCreate, RuleRead, RuleUpdate
from ..security.auth import require_roles

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("/", response_model=RuleRead, summary="Create rule", description="Create a new processing rule.")
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    rule = Rule(name=payload.name, definition=payload.definition, is_active=payload.is_active)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return RuleRead.model_validate(rule.__dict__)


@router.get("/", response_model=List[RuleRead], summary="List rules")
async def list_rules(db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    res = await db.execute(select(Rule))
    rules = res.scalars().all()
    return [RuleRead.model_validate(r.__dict__) for r in rules]


@router.patch("/{rule_id}", response_model=RuleRead, summary="Update rule")
async def update_rule(rule_id: uuid.UUID, payload: RuleUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    res = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if payload.name is not None:
        rule.name = payload.name
    if payload.definition is not None:
        rule.definition = payload.definition
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    await db.commit()
    await db.refresh(rule)
    return RuleRead.model_validate(rule.__dict__)


@router.delete("/{rule_id}", status_code=204, summary="Delete rule")
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_roles("admin"))):
    await db.execute(delete(Rule).where(Rule.id == rule_id))
    await db.commit()
    return None
