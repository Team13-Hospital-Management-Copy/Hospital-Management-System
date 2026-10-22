"""US-03 / HMS-SR-005 / TC-Sec-06: idle session timeout and secure logout."""

from datetime import timedelta

from app.models import AuthToken
from app.rbac import IDLE_TIMEOUT
from app.roles import ADMINISTRATOR

PROTECTED_URL = "/admin/audit-log"  # any require_role(...)-protected endpoint exercises get_current_user


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def age_token(db_session, token: str, age: timedelta) -> None:
    row = db_session.query(AuthToken).filter(AuthToken.token == token).one()
    row.last_seen_at = row.last_seen_at - age
    db_session.commit()


def test_active_session_within_the_timeout_remains_valid(client, db_session, seed_user, login_token):
    seed_user(username="admin1", role=ADMINISTRATOR)
    token = login_token("admin1")

    response = client.get(PROTECTED_URL, headers=auth_header(token))

    assert response.status_code == 200


def test_session_idle_for_more_than_ten_minutes_is_rejected_and_token_removed(
    client, db_session, seed_user, login_token
):
    # AC-HMS-SR-005: an idle session is terminated at 10 minutes and requires re-authentication.
    seed_user(username="admin1", role=ADMINISTRATOR)
    token = login_token("admin1")
    age_token(db_session, token, IDLE_TIMEOUT + timedelta(seconds=1))

    response = client.get(PROTECTED_URL, headers=auth_header(token))

    assert response.status_code == 401
    assert db_session.query(AuthToken).filter(AuthToken.token == token).one_or_none() is None


def test_session_just_under_the_timeout_is_still_valid(client, db_session, seed_user, login_token):
    seed_user(username="admin1", role=ADMINISTRATOR)
    token = login_token("admin1")
    age_token(db_session, token, IDLE_TIMEOUT - timedelta(seconds=1))

    response = client.get(PROTECTED_URL, headers=auth_header(token))

    assert response.status_code == 200


def test_activity_resets_the_idle_clock(client, db_session, seed_user, login_token):
    seed_user(username="admin1", role=ADMINISTRATOR)
    token = login_token("admin1")
    age_token(db_session, token, IDLE_TIMEOUT - timedelta(minutes=1))

    first = client.get(PROTECTED_URL, headers=auth_header(token))
    assert first.status_code == 200

    # The first request should have refreshed last_seen_at, so ageing it again by almost the
    # full timeout (which would have failed against the original, un-refreshed timestamp)
    # still succeeds.
    age_token(db_session, token, IDLE_TIMEOUT - timedelta(seconds=1))
    second = client.get(PROTECTED_URL, headers=auth_header(token))
    assert second.status_code == 200


def test_logout_invalidates_the_token_immediately(client, db_session, seed_user, login_token):
    seed_user(username="admin1", role=ADMINISTRATOR)
    token = login_token("admin1")

    logout_response = client.post("/auth/logout", headers=auth_header(token))
    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "ok"

    reused = client.get(PROTECTED_URL, headers=auth_header(token))
    assert reused.status_code == 401
    assert db_session.query(AuthToken).filter(AuthToken.token == token).one_or_none() is None


def test_logout_without_a_token_does_not_error(client):
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_logout_with_an_already_invalid_token_does_not_error(client):
    response = client.post("/auth/logout", headers=auth_header("not-a-real-token"))

    assert response.status_code == 200
