from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..db.models import AuditLog


# PUBLIC_INTERFACE
def audit_log(db: Session, action: str, performed_by: Optional[UUID], details: Optional[str] = None) -> None:
    """Create an audit log entry.

    Parameters:
    - db: SQLAlchemy Session.
    - action: Action name e.g., 'user.create', 'user.update', 'user.delete'.
    - performed_by: UUID of the user who performed the action (nullable for system actions).
    - details: Optional details string describing the action.
    """
    entry = AuditLog(action=action, performed_by=performed_by, details=details)
    db.add(entry)
    # Do not commit here to avoid interfering with caller transactions; however, in most routes
    # we commit immediately after mutations, so a flush is enough to persist without forcing a separate commit.
    db.flush()
