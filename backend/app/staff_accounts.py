from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, User
from .rbac import require_role
from .roles import ADMINISTRATOR, ALL_ROLES, SYSTEM_ADMINISTRATOR
from .schemas import StaffAccountCreate, StaffAccountOut, StaffAccountUpdate
from .security import hash_password

# US-19 / HMS-F-019: an administrator creates, modifies and deactivates staff accounts and
# assigns roles. RBAC enforcement itself (role checks on every endpoint) is US-04; this story
# is the account-management surface that feeds it.
ADMIN_ROLES = (ADMINISTRATOR, SYSTEM_ADMINISTRATOR)

router = APIRouter(prefix="/admin/staff", tags=["Staff Administration"])


def _validate_role(role: str) -> None:
    if role not in ALL_ROLES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"'{role}' is not a valid role. Must be one of: {sorted(ALL_ROLES)}.",
        )


@router.post(
    "",
    response_model=StaffAccountOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff account",
)
def create_staff_account(
    payload: StaffAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    _validate_role(payload.role)

    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A staff account with this username already exists."
        ) from None

    db.add(
        AuditLogEntry(
            event_type="STAFF_ACCOUNT_CREATED",
            username=current_user.username,
            detail=f"created {user.username} with role {user.role}",
        )
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[StaffAccountOut], summary="List staff accounts")
def list_staff_accounts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    return db.query(User).order_by(User.username).all()


@router.patch(
    "/{username}",
    response_model=StaffAccountOut,
    summary="Modify or deactivate a staff account",
)
def update_staff_account(
    username: str,
    payload: StaffAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    user = db.query(User).filter(User.username == username).one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff account not found.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No changes provided.")

    if "is_active" in changes and changes["is_active"] is False and user.username == current_user.username:
        # Not in the AC, but letting an administrator lock themselves out is a self-inflicted
        # outage with no recovery path in this system (no other way to flip is_active back).
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account.")

    if "role" in changes:
        _validate_role(changes["role"])
        user.role = changes["role"]

    if "is_active" in changes:
        user.is_active = changes["is_active"]

    db.add(
        AuditLogEntry(
            event_type="STAFF_ACCOUNT_UPDATED",
            username=current_user.username,
            detail=f"updated {user.username}: {sorted(changes)}",
        )
    )
    db.commit()
    db.refresh(user)
    return user
