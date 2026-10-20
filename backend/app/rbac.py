import secrets

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, AuthToken, User

AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "
ACCESS_DENIED_MESSAGE = "You do not have permission to access this resource."
INVALID_TOKEN_MESSAGE = "Missing or invalid session token."


def issue_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token=token, user_id=user.id))
    return token


def _extract_token(request: Request) -> str:
    header = request.headers.get(AUTHORIZATION_HEADER, "")
    if not header.startswith(BEARER_PREFIX):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_TOKEN_MESSAGE)
    return header.removeprefix(BEARER_PREFIX)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    auth_token = db.query(AuthToken).filter(AuthToken.token == token).one_or_none()
    user = db.get(User, auth_token.user_id) if auth_token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_TOKEN_MESSAGE)
    return user


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
