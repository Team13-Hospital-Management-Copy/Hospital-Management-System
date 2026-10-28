"""US-19 / HMS-F-019 / TC-Admin-01: create, modify and deactivate staff accounts."""

from app.roles import ADMINISTRATOR, DOCTOR, RECEPTIONIST
from app.models import AuditLogEntry

STAFF_URL = "/admin/staff"


def admin_header(seed_user, login_token, username="admin_us19"):
    seed_user(username=username, role=ADMINISTRATOR)
    return {"Authorization": f"Bearer {login_token(username)}"}


def test_admin_creates_staff_account(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)

    response = client.post(
        STAFF_URL,
        headers=headers,
        json={"username": "new_doctor", "password": "StrongPass123!", "role": DOCTOR},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["username"] == "new_doctor"
    assert data["role"] == DOCTOR
    assert data["is_active"] is True
    assert data["is_locked"] is False
    assert "password" not in data
    assert "password_hash" not in data

    audit = db_session.query(AuditLogEntry).filter_by(event_type="STAFF_ACCOUNT_CREATED").first()
    assert audit is not None
    assert "new_doctor" in audit.detail


def test_non_admin_cannot_create_staff_account(client, db_session, seed_user, login_token):
    seed_user(username="receptionist_us19", role=RECEPTIONIST)
    headers = {"Authorization": f"Bearer {login_token('receptionist_us19')}"}

    response = client.post(
        STAFF_URL,
        headers=headers,
        json={"username": "new_doctor", "password": "StrongPass123!", "role": DOCTOR},
    )

    assert response.status_code == 403


def test_duplicate_username_rejected(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)
    body = {"username": "duplicate_user", "password": "StrongPass123!", "role": DOCTOR}

    assert client.post(STAFF_URL, headers=headers, json=body).status_code == 201
    response = client.post(STAFF_URL, headers=headers, json=body)

    assert response.status_code == 409


def test_invalid_role_rejected(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)

    response = client.post(
        STAFF_URL,
        headers=headers,
        json={"username": "bad_role_user", "password": "StrongPass123!", "role": "SUPERUSER"},
    )

    assert response.status_code == 422


def test_admin_lists_staff_accounts(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)
    client.post(STAFF_URL, headers=headers, json={"username": "listed_user", "password": "StrongPass123!", "role": DOCTOR})

    response = client.get(STAFF_URL, headers=headers)

    assert response.status_code == 200, response.text
    usernames = {u["username"] for u in response.json()}
    assert "admin_us19" in usernames
    assert "listed_user" in usernames


def test_non_admin_cannot_list_staff_accounts(client, db_session, seed_user, login_token):
    seed_user(username="receptionist_list_us19", role=RECEPTIONIST)
    headers = {"Authorization": f"Bearer {login_token('receptionist_list_us19')}"}

    response = client.get(STAFF_URL, headers=headers)

    assert response.status_code == 403


def test_role_change_takes_effect_on_next_request(client, db_session, seed_user, login_token):
    admin = admin_header(seed_user, login_token)
    seed_user(username="promote_me", role=RECEPTIONIST)
    staff_token = login_token("promote_me")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Before promotion: a RECEPTIONIST cannot reach an admin-only endpoint.
    assert client.get(STAFF_URL, headers=staff_headers).status_code == 403

    update = client.patch(f"{STAFF_URL}/promote_me", headers=admin, json={"role": ADMINISTRATOR})
    assert update.status_code == 200, update.text
    assert update.json()["role"] == ADMINISTRATOR

    audit = db_session.query(AuditLogEntry).filter_by(event_type="STAFF_ACCOUNT_UPDATED").first()
    assert audit is not None

    # AC-HMS-F-019: the existing session token reflects the new role immediately, not after
    # a fresh login - get_current_user re-reads the role from the database every request.
    assert client.get(STAFF_URL, headers=staff_headers).status_code == 200


def test_deactivated_account_cannot_log_in(client, db_session, seed_user, login_token):
    admin = admin_header(seed_user, login_token)
    seed_user(username="to_deactivate", role=DOCTOR)

    response = client.patch(f"{STAFF_URL}/to_deactivate", headers=admin, json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    login = client.post(
        "/auth/login", json={"username": "to_deactivate", "password": "CorrectHorseBattery9!"}
    )
    assert login.status_code == 403


def test_deactivation_revokes_an_already_open_session(client, db_session, seed_user, login_token):
    admin = admin_header(seed_user, login_token)
    # A second administrator, so the "before" and "after" checks isolate deactivation itself
    # rather than mixing in a role-permission difference.
    seed_user(username="active_session_user", role=ADMINISTRATOR)
    staff_token = login_token("active_session_user")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # The token is valid before deactivation.
    assert client.get(STAFF_URL, headers=staff_headers).status_code == 200

    client.patch(f"{STAFF_URL}/active_session_user", headers=admin, json={"is_active": False})

    response = client.get(STAFF_URL, headers=staff_headers)
    assert response.status_code == 403


def test_update_unknown_username_returns_404(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)

    response = client.patch(f"{STAFF_URL}/nobody", headers=headers, json={"role": DOCTOR})

    assert response.status_code == 404


def test_update_with_no_fields_rejected(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)
    seed_user(username="no_change_user", role=DOCTOR)

    response = client.patch(f"{STAFF_URL}/no_change_user", headers=headers, json={})

    assert response.status_code == 422


def test_update_with_invalid_role_rejected(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)
    seed_user(username="bad_role_update_user", role=DOCTOR)

    response = client.patch(
        f"{STAFF_URL}/bad_role_update_user", headers=headers, json={"role": "SUPERUSER"}
    )

    assert response.status_code == 422


def test_admin_cannot_deactivate_own_account(client, db_session, seed_user, login_token):
    headers = admin_header(seed_user, login_token)

    response = client.patch(f"{STAFF_URL}/admin_us19", headers=headers, json={"is_active": False})

    assert response.status_code == 400
