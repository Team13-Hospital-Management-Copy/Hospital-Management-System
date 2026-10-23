"""US-08 / HMS-F-005 / TC-Appt-01: book an OPD appointment with real-time slot availability."""

from datetime import date, datetime, timedelta

from app.models import Appointment, AuditLogEntry, Notification
from app.roles import ADMINISTRATOR, DOCTOR, PATIENT, RECEPTIONIST

BOOK_URL = "/appointments/opd"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def setup_world(client, seed_user, login_token) -> tuple[str, str, date]:
    """Admin creates a doctor with a schedule next week; a patient is registered."""
    seed_user(username="admin1", role=ADMINISTRATOR)
    admin = login_token("admin1")
    day = (datetime.utcnow() + timedelta(days=7)).date()
    doctor = client.post(
        "/doctors",
        json={
            "full_name": "Dr. Asha Rao",
            "specialization": "Cardiology",
            "department": "Cardiology",
            "slot_minutes": 30,
            "schedule": [{"weekday": day.weekday(), "start_time": "09:00", "end_time": "10:00"}],
        },
        headers=auth_header(admin),
    ).json()
    patient = client.post(
        "/patients/", json={"full_name": "Meera Iyer", "age": 34, "gender": "F", "phone": "9876543210"}
    ).json()
    seed_user(username="reception1", role=RECEPTIONIST)
    return doctor["doctor_id"], patient["uhid"], day


def slot(day: date, hhmm: str) -> str:
    return f"{day.isoformat()}T{hhmm}:00"


def test_receptionist_books_available_slot_and_it_becomes_unavailable(client, seed_user, login_token, db_session):
    # AC-HMS-F-005: booking succeeds only for an available slot and the slot is then marked unavailable.
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    token = login_token("reception1")

    before = client.get(f"/doctors/{doctor_id}/available-slots", params={"day": day.isoformat()}, headers=auth_header(token))
    booked = client.post(
        BOOK_URL,
        json={"patient_uhid": uhid, "doctor_id": doctor_id, "department": "Cardiology", "slot_start": slot(day, "09:00")},
        headers=auth_header(token),
    )
    after = client.get(f"/doctors/{doctor_id}/available-slots", params={"day": day.isoformat()}, headers=auth_header(token))

    assert booked.status_code == 201, booked.text
    assert booked.json()["status"] == "BOOKED"
    assert slot(day, "09:00") in before.json()["available"]
    assert after.json()["available"] == [slot(day, "09:30")]
    assert db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "APPOINTMENT_BOOKED").count() == 1


def test_second_booking_of_the_same_slot_is_rejected(client, seed_user, login_token):
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    token = login_token("reception1")
    request = {"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "09:30")}

    assert client.post(BOOK_URL, json=request, headers=auth_header(token)).status_code == 201
    assert client.post(BOOK_URL, json=request, headers=auth_header(token)).status_code == 409


def test_slot_outside_the_doctors_schedule_is_rejected(client, seed_user, login_token, db_session):
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    token = login_token("reception1")

    off_hours = client.post(BOOK_URL, json={"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "15:00")}, headers=auth_header(token))
    misaligned = client.post(BOOK_URL, json={"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "09:10")}, headers=auth_header(token))

    assert off_hours.status_code == 409
    assert misaligned.status_code == 409
    assert db_session.query(Appointment).count() == 0


def test_unknown_patient_doctor_or_wrong_department_is_rejected(client, seed_user, login_token):
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    token = login_token("reception1")
    base = {"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "09:00")}

    assert client.post(BOOK_URL, json={**base, "patient_uhid": "HMS-999999"}, headers=auth_header(token)).status_code == 404
    assert client.post(BOOK_URL, json={**base, "doctor_id": "DOC-999999"}, headers=auth_header(token)).status_code == 404
    assert client.post(BOOK_URL, json={**base, "department": "Neurology"}, headers=auth_header(token)).status_code == 422


def test_inactive_doctor_cannot_be_booked(client, seed_user, login_token):
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    admin = login_token("admin1")
    client.patch(f"/doctors/{doctor_id}", json={"is_active": False}, headers=auth_header(admin))
    token = login_token("reception1")

    response = client.post(BOOK_URL, json={"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "09:00")}, headers=auth_header(token))

    assert response.status_code == 409


def test_patient_role_can_book_but_doctor_role_cannot(client, seed_user, login_token):
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    seed_user(username="patient1", role=PATIENT)
    seed_user(username="doc1", role=DOCTOR)
    request = {"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "09:00")}

    assert client.post(BOOK_URL, json=request, headers=auth_header(login_token("doc1"))).status_code == 403
    assert client.post(BOOK_URL, json=request, headers=auth_header(login_token("patient1"))).status_code == 201
    assert client.post(BOOK_URL, json=request).status_code == 401


def test_booking_sends_the_us11_confirmation(client, seed_user, login_token, db_session, gateway):
    doctor_id, uhid, day = setup_world(client, seed_user, login_token)
    token = login_token("reception1")

    booked = client.post(BOOK_URL, json={"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": slot(day, "09:00")}, headers=auth_header(token))

    kinds = {n.kind for n in db_session.query(Notification).filter(Notification.appointment_id == booked.json()["id"])}
    assert kinds == {"CONFIRMATION", "REMINDER"}
    assert any("confirmed" in message for _, _, message in gateway.sent)
