from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...db.models import Rule, User
from ...schemas import RuleCreate, RuleUpdate, RuleOut
from ..deps import get_db, get_current_user, require_admin
from ...utils.audit import audit_log

router = APIRouter(prefix="/rules", tags=["rules"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[RuleOut],
    summary="List rules",
    description="List rules with pagination. Authentication required.",
    responses={
        200: {"description": "List of rules."},
        401: {"description": "Not authenticated."},
    },
)
def list_rules(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user()),
    limit: int = Query(50, ge=1, le=200, description="Max number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
) -> List[RuleOut]:
    """
    Retrieve rules with pagination.
    """
    items = db.query(Rule).order_by(Rule.created_at.desc()).offset(offset).limit(limit).all()
    return [RuleOut.model_validate(i) for i in items]


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=RuleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create rule (admin only)",
    description="Create a new rule. Admin privileges required.",
    responses={
        201: {"description": "Rule created."},
        400: {"description": "Invalid payload."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
    },
)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    current_user: User = Depends(get_current_user()),
) -> RuleOut:
    """
    Create a new Rule.
    """
    rule = Rule(
        name=payload.name,
        definition=payload.definition,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    audit_log(
        db=db,
        action="rule.create",
        performed_by=current_user.id,
        details=f"Created rule {rule.id} name={rule.name} active={rule.is_active}",
    )
    db.commit()  # persist audit entry
    return RuleOut.model_validate(rule)


# PUBLIC_INTERFACE
@router.get(
    "/{rule_id}",
    response_model=RuleOut,
    summary="Get rule by ID",
    description="Retrieve a rule by its ID. Authentication required.",
    responses={
        200: {"description": "Rule returned."},
        401: {"description": "Not authenticated."},
        404: {"description": "Rule not found."},
    },
)
def get_rule_by_id(
    rule_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user()),
) -> RuleOut:
    """
    Get a rule by ID.
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return RuleOut.model_validate(rule)


# PUBLIC_INTERFACE
@router.patch(
    "/{rule_id}",
    response_model=RuleOut,
    summary="Update rule (admin only)",
    description="Update rule name, definition, and/or is_active flag. Admin privileges required.",
    responses={
        200: {"description": "Rule updated."},
        400: {"description": "No changes provided."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
        404: {"description": "Rule not found."},
    },
)
def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    current_user: User = Depends(get_current_user()),
) -> RuleOut:
    """
    Update a rule's name, definition, or is_active flag.
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    changes: list[str] = []
    if payload.name is not None and payload.name != rule.name:
        rule.name = payload.name
        changes.append(f"name={rule.name}")
    if payload.definition is not None and payload.definition != rule.definition:
        rule.definition = payload.definition
        changes.append("definition=updated")
    if payload.is_active is not None and payload.is_active != rule.is_active:
        rule.is_active = payload.is_active
        changes.append(f"is_active={rule.is_active}")

    if not changes:
        # No effective changes; return current state
        return RuleOut.model_validate(rule)

    db.add(rule)
    db.commit()
    db.refresh(rule)

    audit_log(
        db=db,
        action="rule.update",
        performed_by=current_user.id,
        details=f"Updated rule {rule.id}: " + ", ".join(changes),
    )
    db.commit()
    return RuleOut.model_validate(rule)


# PUBLIC_INTERFACE
@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete rule (admin only)",
    description="Delete a rule by ID. Admin privileges required.",
    responses={
        204: {"description": "Rule deleted."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
        404: {"description": "Rule not found."},
    },
)
def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    current_user: User = Depends(get_current_user()),
) -> None:
    """
    Delete an existing rule.
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    rid = rule.id
    rname = rule.name
    db.delete(rule)
    db.commit()

    audit_log(
        db=db,
        action="rule.delete",
        performed_by=current_user.id,
        details=f"Deleted rule {rid} name={rname}",
    )
    return None
