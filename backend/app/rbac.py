import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, AuthToken, User

AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "
ACCESS_DENIED_MESSAGE = "You do not have permission to access this resource."
INVALID_TOKEN_MESSAGE = "Missing or invalid session token."
SESSION_EXPIRED_MESSAGE = "Session expired due to inactivity. Please log in again."

# AC-HMS-SR-005: an idle session is terminated after 10 minutes of inactivity.
IDLE_TIMEOUT = timedelta(minutes=10)


def issue_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token=token, user_id=user.id))
    return token


def _token_from_header(request: Request) -> str | None:
    header = request.headers.get(AUTHORIZATION_HEADER, "")
    if not header.startswith(BEARER_PREFIX):
        return None
    return header.removeprefix(BEARER_PREFIX)


def _extract_token(request: Request) -> str:
    token = _token_from_header(request)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_TOKEN_MESSAGE)
    return token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    auth_token = db.query(AuthToken).filter(AuthToken.token == token).one_or_none()
    if auth_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_TOKEN_MESSAGE)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now - auth_token.last_seen_at > IDLE_TIMEOUT:
        db.delete(auth_token)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED_MESSAGE)

    user = db.get(User, auth_token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_TOKEN_MESSAGE)

    # Activity resets the idle clock (a sliding timeout, not a fixed session lifetime).
    auth_token.last_seen_at = now
    db.commit()
    return user


def revoke_current_token(request: Request, db: Session) -> None:
    """AC-HMS-SR-005: logout immediately invalidates the session token.

    Idempotent: a missing or already-invalid token is not an error, since the caller's
    goal (not being logged in) is already achieved.
    """
    token = _token_from_header(request)
    if token is not None:
        db.query(AuthToken).filter(AuthToken.token == token).delete()
        db.commit()


def require_role(*allowed_roles: str):
    """AC-HMS-SR-002: deny and log access attempts outside a role's permitted scope."""

    def _dependency(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            db.add(
                AuditLogEntry(
                    event_type="ACCESS_DENIED",
                    username=user.username,
                    detail=(
                        f"role={user.role} attempted {request.method} {request.url.path}; "
                        f"requires one of {sorted(allowed_roles)}"
                    ),
                )
            )
            db.commit()
            raise HTTPException(status.HTTP_403_FORBIDDEN, ACCESS_DENIED_MESSAGE)
        return user

    return _dependency
