from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, User
from .rbac import issue_token, revoke_current_token
from .schemas import LoginRequest, LoginResponse, LogoutResponse
from .security import verify_password

router = APIRouter()

# AC-HMS-F-004: lock the account after 5 consecutive failed attempts.
MAX_FAILED_ATTEMPTS = 5

GENERIC_INVALID_CREDENTIALS_MESSAGE = "Invalid username or password."
ACCOUNT_LOCKED_MESSAGE = (
    "Account is locked due to repeated failed login attempts. "
    "Contact an administrator to restore access."
)


def _log(db: Session, event_type: str, username: str, detail: str = "") -> None:
    db.add(AuditLogEntry(event_type=event_type, username=username, detail=detail))


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == payload.username).one_or_none()

    if user is None:
        # Do not reveal whether the username exists.
        _log(db, "LOGIN_FAILURE", payload.username, "unknown username")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_INVALID_CREDENTIALS_MESSAGE)

    if user.is_locked:
        # AC-HMS-SR-006: further attempts against a locked account are blocked and logged.
        _log(db, "LOGIN_BLOCKED_LOCKED_ACCOUNT", user.username)
        db.commit()
        raise HTTPException(status.HTTP_423_LOCKED, ACCOUNT_LOCKED_MESSAGE)

    if verify_password(payload.password, user.password_hash):
        user.failed_login_attempts = 0
        _log(db, "LOGIN_SUCCESS", user.username)
        token = issue_token(db, user)
        db.commit()
        return LoginResponse(status="ok", message="Login successful.", token=token)

    user.failed_login_attempts += 1

    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.is_locked = True
        user.locked_at = datetime.now(timezone.utc)
        _log(
            db,
            "ACCOUNT_LOCKED",
            user.username,
            f"locked after {user.failed_login_attempts} consecutive failed attempts",
        )
        db.commit()
        raise HTTPException(status.HTTP_423_LOCKED, ACCOUNT_LOCKED_MESSAGE)

    _log(
        db,
        "LOGIN_FAILURE",
        user.username,
        f"attempt {user.failed_login_attempts} of {MAX_FAILED_ATTEMPTS}",
    )
    db.commit()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_INVALID_CREDENTIALS_MESSAGE)


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, db: Session = Depends(get_db)) -> LogoutResponse:
    revoke_current_token(request, db)
    return LogoutResponse(status="ok", message="Logged out.")
