"""US-09 / HMS-F-006 / TC-Appt-02: prevent double-booking of a doctor's time slot."""

import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.appointments import SlotUnavailableError, book_appointment
from app.database import Base
from app.models import Appointment
from app.notifications import MockNotificationGateway, utcnow

APPOINTMENTS_URL = "/appointments"


def future_slot(days: int = 3, hour: int = 10) -> datetime:
    return (utcnow() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


def booking(patient: str, doctor: str = "DOC-1", slot: datetime | None = None) -> dict:
    return {"patient_uhid": patient, "doctor_id": doctor, "slot_start": (slot or future_slot()).isoformat()}


def test_second_booking_for_same_doctor_and_slot_is_rejected(client, db_session):
    slot = future_slot()

    first = client.post(APPOINTMENTS_URL, json=booking("UHID-1", slot=slot))
    second = client.post(APPOINTMENTS_URL, json=booking("UHID-2", slot=slot))

    assert first.status_code == 201
    assert second.status_code == 409
    assert db_session.query(Appointment).count() == 1


def test_same_slot_with_different_doctor_and_different_slot_with_same_doctor_are_allowed(client):
    slot = future_slot()

    assert client.post(APPOINTMENTS_URL, json=booking("UHID-1", "DOC-1", slot)).status_code == 201
    assert client.post(APPOINTMENTS_URL, json=booking("UHID-2", "DOC-2", slot)).status_code == 201
    assert (
        client.post(APPOINTMENTS_URL, json=booking("UHID-3", "DOC-1", slot + timedelta(minutes=15))).status_code
        == 201
    )


def test_timezone_variants_of_the_same_instant_count_as_the_same_slot(client):
    # 10:00 UTC and 15:30 IST are the same moment and must not both be bookable.
    slot = future_slot(hour=10)
    utc = slot.isoformat() + "+00:00"
    ist_equivalent = (slot + timedelta(hours=5, minutes=30)).isoformat() + "+05:30"

    assert client.post(APPOINTMENTS_URL, json={**booking("UHID-1"), "slot_start": utc}).status_code == 201
    assert client.post(APPOINTMENTS_URL, json={**booking("UHID-2"), "slot_start": ist_equivalent}).status_code == 409


def test_booking_in_the_past_is_rejected(client):
    past = utcnow() - timedelta(hours=1)
    assert client.post(APPOINTMENTS_URL, json=booking("UHID-1", slot=past)).status_code == 400


def test_booked_slots_endpoint_shows_taken_slots_in_real_time(client):
    slot = future_slot()
    client.post(APPOINTMENTS_URL, json=booking("UHID-1", slot=slot))

    response = client.get("/appointments/booked-slots", params={"doctor_id": "DOC-1", "day": slot.date().isoformat()})

    assert response.status_code == 200
    assert response.json()["booked"] == [slot.isoformat()]


def test_concurrent_booking_attempts_for_same_slot_result_in_exactly_one_success(tmp_path):
    # AC-HMS-F-006: fire many booking attempts at the same instant from separate DB sessions.
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}", connect_args={"timeout": 30})
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False)
    gateway = MockNotificationGateway()
    slot = future_slot()

    attempts = 10
    barrier = threading.Barrier(attempts)
    results: list[str] = []
    lock = threading.Lock()

    def attempt(i: int) -> None:
        with SessionFactory() as db:
            barrier.wait()
            try:
                book_appointment(db, gateway, f"UHID-{i}", "DOC-1", slot)
                outcome = "booked"
            except SlotUnavailableError:
                outcome = "rejected"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("booked") == 1
    assert results.count("rejected") == attempts - 1
    with SessionFactory() as db:
        assert db.query(Appointment).filter(Appointment.doctor_id == "DOC-1").count() == 1
    engine.dispose()


@pytest.mark.parametrize("payload_missing", ["patient_uhid", "doctor_id", "slot_start"])
def test_booking_requires_all_fields(client, payload_missing):
    payload = booking("UHID-1")
    del payload[payload_missing]
    assert client.post(APPOINTMENTS_URL, json=payload).status_code == 422
