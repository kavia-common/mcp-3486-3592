from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ...db.models import AuditLog, User
from ...schemas import AuditLogOut
from ..deps import get_db, require_admin

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[AuditLogOut],
    summary="List audit logs (admin only)",
    description=(
        "Retrieve audit logs with optional filters and pagination. "
        "Admin privileges required. Filters support:\n"
        "- performed_by: UUID of user who performed the action\n"
        "- action: substring match on action field (case-insensitive)\n"
        "- start: timestamp inclusive lower bound\n"
        "- end: timestamp inclusive upper bound\n"
        "Pagination via limit and offset."
    ),
    responses={
        200: {"description": "List of audit logs returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Admin privileges required."},
    },
)
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin()),
    performed_by: Optional[UUID] = Query(None, description="Filter by performer user id (UUID)"),
    action: Optional[str] = Query(None, description="Filter by action name (contains, case-insensitive)"),
    start: Optional[datetime] = Query(None, description="Filter logs from this timestamp (inclusive)"),
    end: Optional[datetime] = Query(None, description="Filter logs up to this timestamp (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip before returning"),
) -> List[AuditLogOut]:
    """
    List audit logs with filters and pagination.

    Parameters:
    - performed_by: UUID filter for the user who performed the action.
    - action: Case-insensitive substring filter on the action field.
    - start: Inclusive lower timestamp bound.
    - end: Inclusive upper timestamp bound.
    - limit/offset: Pagination controls.

    Returns:
    - List[AuditLogOut]: Filtered and paginated audit log entries.
    """
    q = db.query(AuditLog)

    conditions = []
    if performed_by is not None:
        conditions.append(AuditLog.performed_by == performed_by)
    if action:
        # Use ilike for case-insensitive contains
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    if start is not None:
        conditions.append(AuditLog.timestamp >= start)
    if end is not None:
        conditions.append(AuditLog.timestamp <= end)

    if conditions:
        q = q.filter(and_(*conditions))

    # Order by timestamp desc to show newest first
    items = q.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    return [AuditLogOut.model_validate(i) for i in items]
