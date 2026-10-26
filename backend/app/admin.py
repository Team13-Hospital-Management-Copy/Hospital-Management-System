from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry
from .rbac import require_role
from .roles import ADMINISTRATOR, SYSTEM_ADMINISTRATOR

router = APIRouter(tags=["Admin"])


@router.get("/admin/audit-log", summary="View audit log")
def list_audit_log(
    db: Session = Depends(get_db),
    _user=Depends(require_role(ADMINISTRATOR, SYSTEM_ADMINISTRATOR)),
) -> list[dict]:
    """Example AC-HMS-SR-002 protected resource: only administrators may view the audit log."""
    rows = db.query(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "event_type": r.event_type,
            "username": r.username,
            "detail": r.detail,
        }
        for r in rows
    ]
