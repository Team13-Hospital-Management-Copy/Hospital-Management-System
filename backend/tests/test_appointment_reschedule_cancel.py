"""US-10 / HMS-F-007 / TC-Appt-03: reschedule or cancel up to a configurable cutoff."""

from datetime import datetime, timedelta

from app.models import Appointment
from app.notifications import utcnow

APPOINTMENTS_URL = "/appointments"


def future_slot(days: float = 3, hour: int = 10) -> datetime:
    return (utcnow() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


def book(client, patient="UHID-1", doctor="DOC-1", slot=None) -> dict:
    slot = slot or future_slot()
    response = client.post(
        APPOINTMENTS_URL, json={"patient_uhid": patient, "doctor_id": doctor, "slot_start": slot.isoformat()}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cancelling_releases_the_slot_for_another_patient(client, db_session):
    slot = future_slot()
    appointment = book(client, "UHID-1", slot=slot)

    cancelled = client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    rebooked = book(client, "UHID-2", slot=slot)
    assert rebooked["status"] == "BOOKED"


def test_rescheduling_moves_the_booking_without_creating_a_duplicate(client, db_session):
    old_slot = future_slot(hour=10)
    new_slot = future_slot(hour=11)
    appointment = book(client, slot=old_slot)

    response = client.post(
        f"{APPOINTMENTS_URL}/{appointment['id']}/reschedule", json={"new_slot_start": new_slot.isoformat()}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == appointment["id"]
    assert body["slot_start"] == new_slot.isoformat()
    assert body["rescheduled_count"] == 1
    assert db_session.query(Appointment).count() == 1
    # The old slot is free again.
    book(client, "UHID-2", slot=old_slot)


def test_rescheduling_into_a_taken_slot_is_rejected_and_original_is_kept(client, db_session):
    slot_a = future_slot(hour=10)
    slot_b = future_slot(hour=11)
    mine = book(client, "UHID-1", slot=slot_a)
    book(client, "UHID-2", slot=slot_b)

    response = client.post(
        f"{APPOINTMENTS_URL}/{mine['id']}/reschedule", json={"new_slot_start": slot_b.isoformat()}
    )

    assert response.status_code == 409
    assert client.get(f"{APPOINTMENTS_URL}/{mine['id']}").json()["slot_start"] == slot_a.isoformat()


def test_change_inside_cutoff_window_is_rejected(client, monkeypatch):
    monkeypatch.setenv("APPOINTMENT_CHANGE_CUTOFF_HOURS", "2")
    soon = (utcnow() + timedelta(hours=1)).replace(second=0, microsecond=0)
    appointment = book(client, slot=soon)

    cancel = client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel")
    move = client.post(
        f"{APPOINTMENTS_URL}/{appointment['id']}/reschedule",
        json={"new_slot_start": future_slot().isoformat()},
    )

    assert cancel.status_code == 400
    assert "2 hour" in cancel.json()["detail"]
    assert move.status_code == 400


def test_cutoff_is_configurable(client, monkeypatch):
    soon = (utcnow() + timedelta(hours=1)).replace(second=0, microsecond=0)
    appointment = book(client, slot=soon)

    monkeypatch.setenv("APPOINTMENT_CHANGE_CUTOFF_HOURS", "0.5")

    assert client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel").status_code == 200


def test_cancelling_twice_or_unknown_appointment_is_rejected(client):
    appointment = book(client)
    client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel")

    assert client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel").status_code == 409
    assert client.post(f"{APPOINTMENTS_URL}/999/cancel").status_code == 404


def test_cannot_reschedule_a_cancelled_appointment_or_into_the_past(client):
    appointment = book(client)
    past = utcnow() - timedelta(hours=1)
    assert (
        client.post(
            f"{APPOINTMENTS_URL}/{appointment['id']}/reschedule", json={"new_slot_start": past.isoformat()}
        ).status_code
        == 400
    )

    client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel")
    assert (
        client.post(
            f"{APPOINTMENTS_URL}/{appointment['id']}/reschedule",
            json={"new_slot_start": future_slot(hour=12).isoformat()},
        ).status_code
        == 409
    )
