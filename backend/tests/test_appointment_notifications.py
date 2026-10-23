"""US-11 / HMS-F-008 / TC-Appt-04: confirmation within 1 minute of booking, reminder 24h prior."""

from datetime import datetime, timedelta

from app.models import Notification
from app.notifications import REMINDER_LEAD_TIME, dispatch_due_notifications, utcnow

APPOINTMENTS_URL = "/appointments"


def future_slot(days: float = 3, hour: int = 10) -> datetime:
    return (utcnow() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


def book(client, headers, patient="UHID-1", slot=None) -> dict:
    slot = slot or future_slot()
    response = client.post(
        APPOINTMENTS_URL,
        json={"patient_uhid": patient, "doctor_id": "DOC-1", "slot_start": slot.isoformat()},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def notifications(db_session, appointment_id, kind=None):
    query = db_session.query(Notification).filter(Notification.appointment_id == appointment_id)
    if kind:
        query = query.filter(Notification.kind == kind)
    return query.all()


def test_confirmation_is_sent_within_one_minute_of_booking_on_every_channel(
    client, db_session, gateway, receptionist_header
):
    before = utcnow()
    appointment = book(client, receptionist_header)

    confirmations = notifications(db_session, appointment["id"], "CONFIRMATION")

    assert {n.channel for n in confirmations} == {"SMS", "EMAIL"}
    for n in confirmations:
        assert n.status == "SENT"
        assert n.sent_at - before < timedelta(minutes=1)
    assert len(gateway.sent) == 2
    assert all("confirmed" in message for _, _, message in gateway.sent)


def test_reminder_is_scheduled_24_hours_before_and_sent_when_due(client, db_session, gateway, receptionist_header):
    slot = future_slot()
    appointment = book(client, receptionist_header, slot=slot)
    reminders = notifications(db_session, appointment["id"], "REMINDER")
    assert len(reminders) == 2
    assert all(r.scheduled_for == slot - REMINDER_LEAD_TIME and r.status == "PENDING" for r in reminders)

    gateway.sent.clear()
    assert dispatch_due_notifications(db_session, gateway, now=slot - REMINDER_LEAD_TIME - timedelta(minutes=1)) == 0
    assert gateway.sent == []

    assert dispatch_due_notifications(db_session, gateway, now=slot - REMINDER_LEAD_TIME) == 2
    assert all("Reminder" in message for _, _, message in gateway.sent)
    for r in reminders:
        db_session.refresh(r)
        assert r.status == "SENT"

    # Already-sent reminders are not sent again.
    assert dispatch_due_notifications(db_session, gateway, now=slot) == 0


def test_booking_less_than_24_hours_ahead_sends_confirmation_only(client, db_session, receptionist_header):
    appointment = book(client, receptionist_header, slot=utcnow() + timedelta(hours=5))

    assert notifications(db_session, appointment["id"], "REMINDER") == []
    assert len(notifications(db_session, appointment["id"], "CONFIRMATION")) == 2


def test_cancelling_stops_the_reminder_and_notifies_the_patient(client, db_session, gateway, receptionist_header):
    slot = future_slot()
    appointment = book(client, receptionist_header, slot=slot)
    gateway.sent.clear()

    client.post(f"{APPOINTMENTS_URL}/{appointment['id']}/cancel", headers=receptionist_header)

    assert all(r.status == "CANCELLED" for r in notifications(db_session, appointment["id"], "REMINDER"))
    assert len(notifications(db_session, appointment["id"], "CANCELLATION")) == 2
    gateway.sent.clear()
    assert dispatch_due_notifications(db_session, gateway, now=slot) == 0


def test_rescheduling_moves_the_reminder_and_sends_a_new_confirmation(
    client, db_session, gateway, receptionist_header
):
    old_slot = future_slot(days=3)
    new_slot = future_slot(days=5)
    appointment = book(client, receptionist_header, slot=old_slot)

    client.post(
        f"{APPOINTMENTS_URL}/{appointment['id']}/reschedule",
        json={"new_slot_start": new_slot.isoformat()},
        headers=receptionist_header,
    )

    reminders = notifications(db_session, appointment["id"], "REMINDER")
    pending = [r for r in reminders if r.status == "PENDING"]
    assert {r.scheduled_for for r in pending} == {new_slot - REMINDER_LEAD_TIME}
    assert all(r.status == "CANCELLED" for r in reminders if r not in pending)
    assert len(notifications(db_session, appointment["id"], "CONFIRMATION")) == 4
    assert "moved" in gateway.sent[-1][2]


def test_gateway_failure_does_not_block_booking_and_is_retried(client, db_session, gateway, receptionist_header):
    original_send = gateway.send

    def failing_send(channel, recipient, message):
        raise ConnectionError("SMS gateway unreachable")

    gateway.send = failing_send
    appointment = book(client, receptionist_header)
    confirmations = notifications(db_session, appointment["id"], "CONFIRMATION")
    assert all(n.status == "FAILED" and "unreachable" in n.last_error for n in confirmations)

    gateway.send = original_send
    assert dispatch_due_notifications(db_session, gateway) == 2
    for n in confirmations:
        db_session.refresh(n)
        assert n.status == "SENT"


def test_notification_history_endpoint_lists_what_was_sent(client, receptionist_header):
    appointment = book(client, receptionist_header)

    response = client.get(f"{APPOINTMENTS_URL}/{appointment['id']}/notifications", headers=receptionist_header)

    assert response.status_code == 200
    kinds = sorted({n["kind"] for n in response.json()})
    assert kinds == ["CONFIRMATION", "REMINDER"]


def test_notification_history_requires_login(client, receptionist_header):
    appointment = book(client, receptionist_header)

    assert client.get(f"{APPOINTMENTS_URL}/{appointment['id']}/notifications").status_code == 401
