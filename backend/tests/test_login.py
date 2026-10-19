from app.auth import MAX_FAILED_ATTEMPTS
from app.models import AuditLogEntry, User

LOGIN_URL = "/auth/login"
CORRECT_PASSWORD = "CorrectHorseBattery9!"
WRONG_PASSWORD = "wrong-password"


def test_password_is_stored_as_salted_hash_not_plaintext(db_session, seed_user):
    # AC-HMS-SR-004
    user = seed_user(password=CORRECT_PASSWORD)
    assert user.password_hash != CORRECT_PASSWORD
    assert user.password_hash.startswith("$2b$")


def test_successful_login_returns_ok_and_resets_failed_count(client, db_session, seed_user):
    user = seed_user(password=CORRECT_PASSWORD)
    user.failed_login_attempts = 2
    db_session.commit()

    response = client.post(LOGIN_URL, json={"username": user.username, "password": CORRECT_PASSWORD})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    db_session.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.is_locked is False

    success_entries = (
        db_session.query(AuditLogEntry)
        .filter(AuditLogEntry.event_type == "LOGIN_SUCCESS", AuditLogEntry.username == user.username)
        .all()
    )
    assert len(success_entries) == 1


def test_failed_login_increments_counter_and_is_logged(client, db_session, seed_user):
    user = seed_user(password=CORRECT_PASSWORD)

    response = client.post(LOGIN_URL, json={"username": user.username, "password": WRONG_PASSWORD})

    assert response.status_code == 401
    db_session.refresh(user)
    assert user.failed_login_attempts == 1
    assert user.is_locked is False

    failure_entries = (
        db_session.query(AuditLogEntry)
        .filter(AuditLogEntry.event_type == "LOGIN_FAILURE", AuditLogEntry.username == user.username)
        .all()
    )
    assert len(failure_entries) == 1


def test_fifth_consecutive_failure_locks_account_and_logs_it(client, db_session, seed_user):
    # AC-HMS-F-004: after 5 consecutive failed attempts the account is locked and audited.
    user = seed_user(password=CORRECT_PASSWORD)

    for _ in range(MAX_FAILED_ATTEMPTS - 1):
        resp = client.post(LOGIN_URL, json={"username": user.username, "password": WRONG_PASSWORD})
        assert resp.status_code == 401

    db_session.refresh(user)
    assert user.is_locked is False

    fifth_response = client.post(LOGIN_URL, json={"username": user.username, "password": WRONG_PASSWORD})

    assert fifth_response.status_code == 423
    db_session.refresh(user)
    assert user.is_locked is True
    assert user.failed_login_attempts == MAX_FAILED_ATTEMPTS

    locked_entries = (
        db_session.query(AuditLogEntry)
        .filter(AuditLogEntry.event_type == "ACCOUNT_LOCKED", AuditLogEntry.username == user.username)
        .all()
    )
    assert len(locked_entries) == 1


def test_sixth_attempt_on_locked_account_is_blocked_even_with_correct_password(client, db_session, seed_user):
    # AC-HMS-SR-006: a locked account rejects further attempts and logs each one.
    user = seed_user(password=CORRECT_PASSWORD)
    for _ in range(MAX_FAILED_ATTEMPTS):
        client.post(LOGIN_URL, json={"username": user.username, "password": WRONG_PASSWORD})

    db_session.refresh(user)
    assert user.is_locked is True

    sixth_response = client.post(LOGIN_URL, json={"username": user.username, "password": CORRECT_PASSWORD})

    assert sixth_response.status_code == 423
    db_session.refresh(user)
    assert user.failed_login_attempts == MAX_FAILED_ATTEMPTS  # unchanged, attempt was blocked outright

    blocked_entries = (
        db_session.query(AuditLogEntry)
        .filter(
            AuditLogEntry.event_type == "LOGIN_BLOCKED_LOCKED_ACCOUNT",
            AuditLogEntry.username == user.username,
        )
        .all()
    )
    assert len(blocked_entries) == 1


def test_unknown_username_returns_generic_message(client, db_session):
    response = client.post(LOGIN_URL, json={"username": "no-such-user", "password": "anything"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."
    assert db_session.query(User).filter(User.username == "no-such-user").one_or_none() is None
