"""US-04 / HMS-SR-002 / TC-Sec-03: access outside a role's permitted scope is denied and logged."""

from app.models import AuditLogEntry
from app.roles import ADMINISTRATOR, PHARMACIST, RECEPTIONIST, SYSTEM_ADMINISTRATOR

AUDIT_LOG_URL = "/admin/audit-log"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_request_without_a_token_is_rejected(client, seed_user):
    seed_user(role=ADMINISTRATOR)

    response = client.get(AUDIT_LOG_URL)

    assert response.status_code == 401


def test_request_with_a_garbage_token_is_rejected(client, seed_user):
    seed_user(role=ADMINISTRATOR)

    response = client.get(AUDIT_LOG_URL, headers=auth_header("not-a-real-token"))

    assert response.status_code == 401


def test_administrator_can_view_the_audit_log(client, seed_user, login_token):
    seed_user(username="admin1", role=ADMINISTRATOR)
    token = login_token("admin1")

    response = client.get(AUDIT_LOG_URL, headers=auth_header(token))

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_system_administrator_can_also_view_the_audit_log(client, seed_user, login_token):
    seed_user(username="sysadmin1", role=SYSTEM_ADMINISTRATOR)
    token = login_token("sysadmin1")

    response = client.get(AUDIT_LOG_URL, headers=auth_header(token))

    assert response.status_code == 200


def test_receptionist_cannot_view_the_audit_log_and_the_denial_is_logged(client, db_session, seed_user, login_token):
    # Mirrors the exact example in AC-HMS-SR-002: a receptionist is denied access outside their scope.
    seed_user(username="reception1", role=RECEPTIONIST)
    token = login_token("reception1")

    response = client.get(AUDIT_LOG_URL, headers=auth_header(token))

    assert response.status_code == 403

    denied_entries = (
        db_session.query(AuditLogEntry)
        .filter(AuditLogEntry.event_type == "ACCESS_DENIED", AuditLogEntry.username == "reception1")
        .all()
    )
    assert len(denied_entries) == 1
    assert "/admin/audit-log" in denied_entries[0].detail


def test_pharmacist_cannot_view_the_audit_log(client, seed_user, login_token):
    # Second example from AC-HMS-SR-002: a pharmacist is outside billing/admin scope.
    seed_user(username="pharm1", role=PHARMACIST)
    token = login_token("pharm1")

    response = client.get(AUDIT_LOG_URL, headers=auth_header(token))

    assert response.status_code == 403
