import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Protocol

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .database import get_db
from .models import Appointment, Notification

logger = logging.getLogger("hms.notifications")

router = APIRouter()

# AC-HMS-F-008: a reminder is sent 24 hours before the appointment.
REMINDER_LEAD_TIME = timedelta(hours=24)

# A failed send is retried by the dispatcher until it has been attempted this many times.
MAX_SEND_ATTEMPTS = 3

KIND_CONFIRMATION = "CONFIRMATION"
KIND_REMINDER = "REMINDER"
KIND_CANCELLATION = "CANCELLATION"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def notification_channels() -> list[str]:
    """Channels to notify on, e.g. "SMS,EMAIL". Read at call time so it can be changed per environment."""
    raw = os.environ.get("NOTIFICATION_CHANNELS", "SMS,EMAIL")
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


class NotificationGateway(Protocol):
    def send(self, channel: str, recipient: str, message: str) -> None:
        """Deliver one message. Raise an exception if delivery fails."""


class MockNotificationGateway:
    """Stand-in for the external SMS/e-mail gateway (see Sprint playbook §9, US-11 risk).

    It records every message instead of delivering it. Swap in a real gateway by overriding
    the `get_gateway` dependency once one is available.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, channel: str, recipient: str, message: str) -> None:
        self.sent.append((channel, recipient, message))
        logger.info("[MOCK %s] to %s: %s", channel, recipient, message)


_gateway = MockNotificationGateway()


def get_gateway() -> NotificationGateway:
    return _gateway


def _format_slot(slot_start: datetime) -> str:
    return slot_start.strftime("%d %b %Y, %H:%M UTC")


def _deliver(notification: Notification, gateway: NotificationGateway, now: datetime) -> None:
    notification.attempts += 1
    try:
        gateway.send(notification.channel, notification.recipient, notification.message)
    except Exception as exc:  # noqa: BLE001 - any gateway failure must not break the caller
        notification.status = "FAILED"
        notification.last_error = str(exc)[:500]
        logger.warning("Notification %s failed: %s", notification.id, exc)
        return
    notification.status = "SENT"
    notification.sent_at = now
    notification.last_error = ""


def _send_now(
    db: Session, gateway: NotificationGateway, appointment: Appointment, kind: str, message: str, now: datetime
) -> None:
    for channel in notification_channels():
        notification = Notification(
            appointment_id=appointment.id,
            kind=kind,
            channel=channel,
            # Until US-05 (Patient Registration) exposes contact details, the UHID identifies the
            # recipient and the gateway is responsible for resolving it to a phone number / e-mail.
            recipient=appointment.patient_uhid,
            message=message,
            scheduled_for=now,
        )
        db.add(notification)
        db.flush()
        _deliver(notification, gateway, now)


def _schedule_reminders(db: Session, appointment: Appointment, now: datetime) -> None:
    remind_at = appointment.slot_start - REMINDER_LEAD_TIME
    if remind_at <= now:
        # Booked less than 24h ahead: the confirmation just sent already serves as the reminder.
        return
    message = (
        f"Reminder: you have an appointment (#{appointment.id}) with doctor {appointment.doctor_id} "
        f"on {_format_slot(appointment.slot_start)}."
    )
    for channel in notification_channels():
        db.add(
            Notification(
                appointment_id=appointment.id,
                kind=KIND_REMINDER,
                channel=channel,
                recipient=appointment.patient_uhid,
                message=message,
                scheduled_for=remind_at,
            )
        )


def _cancel_pending_reminders(db: Session, appointment: Appointment) -> None:
    pending = (
        db.query(Notification)
        .filter(
            Notification.appointment_id == appointment.id,
            Notification.kind == KIND_REMINDER,
            Notification.status.in_(["PENDING", "FAILED"]),
        )
        .all()
    )
    for notification in pending:
        notification.status = "CANCELLED"


def on_appointment_booked(db: Session, gateway: NotificationGateway, appointment: Appointment, now: datetime) -> None:
    # AC-HMS-F-008: the confirmation is sent synchronously as part of the booking request, so it
    # goes out well within 1 minute; the reminder is queued for 24h before the slot.
    message = (
        f"Your appointment (#{appointment.id}) with doctor {appointment.doctor_id} is confirmed for "
        f"{_format_slot(appointment.slot_start)}."
    )
    _send_now(db, gateway, appointment, KIND_CONFIRMATION, message, now)
    _schedule_reminders(db, appointment, now)


def on_appointment_rescheduled(
    db: Session, gateway: NotificationGateway, appointment: Appointment, now: datetime
) -> None:
    _cancel_pending_reminders(db, appointment)
    message = (
        f"Your appointment (#{appointment.id}) with doctor {appointment.doctor_id} has been moved to "
        f"{_format_slot(appointment.slot_start)}."
    )
    _send_now(db, gateway, appointment, KIND_CONFIRMATION, message, now)
    _schedule_reminders(db, appointment, now)


def on_appointment_cancelled(
    db: Session, gateway: NotificationGateway, appointment: Appointment, now: datetime
) -> None:
    _cancel_pending_reminders(db, appointment)
    message = (
        f"Your appointment (#{appointment.id}) with doctor {appointment.doctor_id} on "
        f"{_format_slot(appointment.slot_start)} has been cancelled."
    )
    _send_now(db, gateway, appointment, KIND_CANCELLATION, message, now)


def dispatch_due_notifications(db: Session, gateway: NotificationGateway, now: datetime | None = None) -> int:
    """Send reminders whose time has come and retry earlier sends that failed.

    Reminders for cancelled or moved appointments are already marked CANCELLED, so they are skipped.
    Returns how many notifications were sent successfully.
    """
    now = now or utcnow()
    due = (
        db.query(Notification)
        .filter(
            Notification.scheduled_for <= now,
            Notification.status.in_(["PENDING", "FAILED"]),
            Notification.attempts < MAX_SEND_ATTEMPTS,
        )
        .order_by(Notification.id)
        .all()
    )
    sent = 0
    for notification in due:
        _deliver(notification, gateway, now)
        sent += notification.status == "SENT"
    db.commit()
    return sent


@router.post("/notifications/dispatch-due")
def dispatch_due(db: Session = Depends(get_db), gateway: NotificationGateway = Depends(get_gateway)) -> dict:
    """Trigger for a scheduler/cron job; the app also runs this periodically in the background."""
    return {"sent": dispatch_due_notifications(db, gateway)}


@router.get("/appointments/{appointment_id}/notifications")
def list_notifications(appointment_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Notification)
        .filter(Notification.appointment_id == appointment_id)
        .order_by(Notification.id)
        .all()
    )
    return [
        {
            "id": n.id,
            "kind": n.kind,
            "channel": n.channel,
            "status": n.status,
            "scheduled_for": n.scheduled_for,
            "sent_at": n.sent_at,
            "message": n.message,
        }
        for n in rows
    ]
