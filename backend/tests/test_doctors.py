"""US-07 / TC-DOC: doctor profiles with a configurable weekly slot schedule."""

from datetime import date, datetime, timedelta

from app.models import AuditLogEntry
from app.roles import ADMINISTRATOR, DOCTOR, RECEPTIONIST

DOCTORS_URL = "/doctors"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def next_week_day() -> date:
    return (datetime.utcnow() + timedelta(days=7)).date()


def doctor_payload(day: date, **overrides) -> dict:
    payload = {
        "full_name": "Dr. Asha Rao",
        "specialization": "Cardiology",
        "department": "Cardiology",
        "slot_minutes": 30,
        "schedule": [{"weekday": day.weekday(), "start_time": "09:00", "end_time": "11:00"}],
    }
    payload.update(overrides)
    return payload


def admin_token(seed_user, login_token) -> str:
    seed_user(username="admin1", role=ADMINISTRATOR)
    return login_token("admin1")


def test_admin_creates_doctor_with_profile_and_weekly_schedule(client, seed_user, login_token):
    token = admin_token(seed_user, login_token)
    day = next_week_day()

    response = client.post(DOCTORS_URL, json=doctor_payload(day), headers=auth_header(token))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["doctor_id"] == "DOC-000001"
    assert body["full_name"] == "Dr. Asha Rao"
    assert body["specialization"] == "Cardiology"
    assert body["department"] == "Cardiology"
    assert body["schedule"] == [{"weekday": day.weekday(), "start_time": "09:00:00", "end_time": "11:00:00"}]


def test_non_admin_cannot_create_or_change_doctors(client, seed_user, login_token, db_session):
    seed_user(username="reception1", role=RECEPTIONIST)
    token = login_token("reception1")

    response = client.post(DOCTORS_URL, json=doctor_payload(next_week_day()), headers=auth_header(token))

    assert response.status_code == 403
    assert db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "ACCESS_DENIED").count() == 1


def test_creating_a_doctor_requires_login(client):
    assert client.post(DOCTORS_URL, json=doctor_payload(next_week_day())).status_code == 401


def test_available_slots_follow_the_schedule(client, seed_user, login_token):
    token = admin_token(seed_user, login_token)
    day = next_week_day()
    client.post(DOCTORS_URL, json=doctor_payload(day), headers=auth_header(token))

    response = client.get(f"{DOCTORS_URL}/DOC-000001/available-slots", params={"day": day.isoformat()}, headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["available"] == [f"{day.isoformat()}T{t}" for t in ("09:00:00", "09:30:00", "10:00:00", "10:30:00")]


def test_no_slots_on_days_without_a_schedule_block(client, seed_user, login_token):
    token = admin_token(seed_user, login_token)
    day = next_week_day()
    client.post(DOCTORS_URL, json=doctor_payload(day), headers=auth_header(token))

    other_day = day + timedelta(days=1)
    response = client.get(f"{DOCTORS_URL}/DOC-000001/available-slots", params={"day": other_day.isoformat()}, headers=auth_header(token))

    assert response.json()["available"] == []


def test_schedule_change_is_reflected_immediately_in_availability(client, seed_user, login_token, db_session):
    # US-07 AC: slot schedule changes are immediately reflected in availability queries.
    token = admin_token(seed_user, login_token)
    day = next_week_day()
    client.post(DOCTORS_URL, json=doctor_payload(day), headers=auth_header(token))

    new_schedule = [{"weekday": day.weekday(), "start_time": "14:00", "end_time": "15:00"}]
    put = client.put(f"{DOCTORS_URL}/DOC-000001/schedule", json=new_schedule, headers=auth_header(token))
    slots = client.get(f"{DOCTORS_URL}/DOC-000001/available-slots", params={"day": day.isoformat()}, headers=auth_header(token))

    assert put.status_code == 200
    assert slots.json()["available"] == [f"{day.isoformat()}T14:00:00", f"{day.isoformat()}T14:30:00"]
    assert db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "DOCTOR_SCHEDULE_UPDATED").count() == 1


def test_overlapping_or_backwards_schedule_blocks_are_rejected(client, seed_user, login_token):
    token = admin_token(seed_user, login_token)
    day = next_week_day()
    overlapping = [
        {"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
        {"weekday": 0, "start_time": "11:00", "end_time": "13:00"},
    ]
    backwards = [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}]

    assert client.post(DOCTORS_URL, json=doctor_payload(day, schedule=overlapping), headers=auth_header(token)).status_code == 422
    assert client.post(DOCTORS_URL, json=doctor_payload(day, schedule=backwards), headers=auth_header(token)).status_code == 422


def test_update_profile_and_deactivate_doctor(client, seed_user, login_token):
    token = admin_token(seed_user, login_token)
    day = next_week_day()
    client.post(DOCTORS_URL, json=doctor_payload(day), headers=auth_header(token))

    patched = client.patch(f"{DOCTORS_URL}/DOC-000001", json={"department": "Cardiac Sciences", "is_active": False}, headers=auth_header(token))

    assert patched.status_code == 200
    assert patched.json()["department"] == "Cardiac Sciences"
    assert patched.json()["is_active"] is False
    slots = client.get(f"{DOCTORS_URL}/DOC-000001/available-slots", params={"day": day.isoformat()}, headers=auth_header(token))
    assert slots.json()["available"] == []
    assert client.get(DOCTORS_URL, headers=auth_header(token)).json() == []


def test_any_logged_in_user_can_list_and_filter_doctors(client, seed_user, login_token):
    token = admin_token(seed_user, login_token)
    day = next_week_day()
    client.post(DOCTORS_URL, json=doctor_payload(day), headers=auth_header(token))
    client.post(DOCTORS_URL, json=doctor_payload(day, full_name="Dr. Ravi K", specialization="Orthopaedics", department="Orthopaedics"), headers=auth_header(token))
    seed_user(username="doc1", role=DOCTOR)
    doctor_token = login_token("doc1")

    everyone = client.get(DOCTORS_URL, headers=auth_header(doctor_token))
    ortho = client.get(DOCTORS_URL, params={"department": "orthopaedics"}, headers=auth_header(doctor_token))

    assert [d["doctor_id"] for d in everyone.json()] == ["DOC-000001", "DOC-000002"]
    assert [d["full_name"] for d in ortho.json()] == ["Dr. Ravi K"]
    assert client.get(f"{DOCTORS_URL}/DOC-999999", headers=auth_header(doctor_token)).status_code == 404
