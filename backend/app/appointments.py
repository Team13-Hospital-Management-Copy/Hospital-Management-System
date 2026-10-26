import os
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import APPOINTMENT_STATUS_BOOKED, APPOINTMENT_STATUS_CANCELLED, Appointment, User
from .notifications import (
    NotificationGateway,
    get_gateway,
    on_appointment_booked,
    on_appointment_cancelled,
    on_appointment_rescheduled,
    utcnow,
)
from .rbac import get_current_user, require_role
from .roles import PATIENT, RECEPTIONIST
from .schemas import AppointmentCreate, AppointmentOut, AppointmentReschedule

# HMS-F-005/006/007: a patient or receptionist creates, cancels or reschedules appointments.
BOOKING_ROLES = (RECEPTIONIST, PATIENT)

router = APIRouter(tags=["Appointments"])

SLOT_UNAVAILABLE_MESSAGE = "This time slot is no longer available for the selected doctor."
DEFAULT_CHANGE_CUTOFF_HOURS = 2.0


class SlotUnavailableError(Exception):
    pass


class AppointmentChangeError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def change_cutoff() -> timedelta:
    """HMS-F-007: how close to the slot a reschedule/cancel is still allowed.

    Configured with APPOINTMENT_CHANGE_CUTOFF_HOURS (read at call time). Moving this into an
    admin-editable setting belongs with US-19 (Staff Account & Role Administration).
    """
    return timedelta(hours=float(os.environ.get("APPOINTMENT_CHANGE_CUTOFF_HOURS", DEFAULT_CHANGE_CUTOFF_HOURS)))


def to_utc_naive(value: datetime) -> datetime:
    """Normalise to naive UTC so the same instant always maps to the same stored value."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(second=0, microsecond=0)


# --- Service functions: US-08's booking UI/endpoint should call book_appointment() -----------


def book_appointment(
    db: Session,
    gateway: NotificationGateway,
    patient_uhid: str,
    doctor_id: str,
    slot_start: datetime,
    now: datetime | None = None,
) -> Appointment:
    now = now or utcnow()
    slot_start = to_utc_naive(slot_start)
    if slot_start <= now:
        raise AppointmentChangeError(status.HTTP_400_BAD_REQUEST, "Cannot book a slot in the past.")

    appointment = Appointment(patient_uhid=patient_uhid, doctor_id=doctor_id, slot_start=slot_start)
    db.add(appointment)
    try:
        # AC-HMS-F-006: the partial unique index rejects a second active booking for this
        # doctor/slot, even when two requests race each other.
        db.flush()
    except IntegrityError:
        db.rollback()
        raise SlotUnavailableError from None

    on_appointment_booked(db, gateway, appointment, now)
    db.commit()
    db.refresh(appointment)
    return appointment


def _get_active(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise AppointmentChangeError(status.HTTP_404_NOT_FOUND, "Appointment not found.")
    if appointment.status != APPOINTMENT_STATUS_BOOKED:
        raise AppointmentChangeError(status.HTTP_409_CONFLICT, "Appointment is already cancelled.")
    return appointment


def _check_cutoff(appointment: Appointment, now: datetime) -> None:
    if appointment.slot_start - now < change_cutoff():
        hours = change_cutoff().total_seconds() / 3600
        raise AppointmentChangeError(
            status.HTTP_400_BAD_REQUEST,
            f"Appointments can only be changed up to {hours:g} hour(s) before the slot.",
        )


def cancel_appointment(
    db: Session, gateway: NotificationGateway, appointment_id: int, now: datetime | None = None
) -> Appointment:
    now = now or utcnow()
    appointment = _get_active(db, appointment_id)
    _check_cutoff(appointment, now)

    # AC-HMS-F-007: cancelling releases the slot (the unique index only covers BOOKED rows).
    appointment.status = APPOINTMENT_STATUS_CANCELLED
    appointment.cancelled_at = now
    on_appointment_cancelled(db, gateway, appointment, now)
    db.commit()
    db.refresh(appointment)
    return appointment


def reschedule_appointment(
    db: Session,
    gateway: NotificationGateway,
    appointment_id: int,
    new_slot_start: datetime,
    now: datetime | None = None,
) -> Appointment:
    now = now or utcnow()
    appointment = _get_active(db, appointment_id)
    _check_cutoff(appointment, now)

    new_slot_start = to_utc_naive(new_slot_start)
    if new_slot_start <= now:
        raise AppointmentChangeError(status.HTTP_400_BAD_REQUEST, "Cannot move an appointment into the past.")
    if new_slot_start == appointment.slot_start:
        raise AppointmentChangeError(status.HTTP_400_BAD_REQUEST, "The new slot is the same as the current one.")

    # AC-HMS-F-007: the existing row is moved, so no duplicate booking is created and the old slot
    # is freed in the same transaction.
    appointment.slot_start = new_slot_start
    appointment.rescheduled_count += 1
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise SlotUnavailableError from None

    on_appointment_rescheduled(db, gateway, appointment, now)
    db.commit()
    db.refresh(appointment)
    return appointment


def booked_slots(db: Session, doctor_id: str, day: date) -> list[datetime]:
    start = datetime.combine(day, time.min)
    rows = (
        db.query(Appointment.slot_start)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == APPOINTMENT_STATUS_BOOKED,
            Appointment.slot_start >= start,
            Appointment.slot_start < start + timedelta(days=1),
        )
        .order_by(Appointment.slot_start)
        .all()
    )
    return [r.slot_start for r in rows]


# --- HTTP endpoints --------------------------------------------------------------------------


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SlotUnavailableError):
        return HTTPException(status.HTTP_409_CONFLICT, SLOT_UNAVAILABLE_MESSAGE)
    assert isinstance(exc, AppointmentChangeError)
    return HTTPException(exc.status_code, exc.message)


@router.post(
    "/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an appointment (low-level)",
)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    gateway: NotificationGateway = Depends(get_gateway),
    _user: User = Depends(require_role(*BOOKING_ROLES)),
) -> Appointment:
    # Low-level booking call: it does not check that the patient/doctor exist or that the slot is
    # on the doctor's schedule. Front ends should use POST /appointments/opd (US-08) instead.
    try:
        return book_appointment(db, gateway, payload.patient_uhid, payload.doctor_id, payload.slot_start)
    except (SlotUnavailableError, AppointmentChangeError) as exc:
        raise _http_error(exc) from None


@router.get("/appointments/booked-slots", summary="List booked slots for a doctor")
def get_booked_slots(
    doctor_id: str, day: date, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    """HMS-F-006: real-time view of which slots are taken for a doctor on a given day (UTC)."""
    return {"doctor_id": doctor_id, "day": day, "booked": booked_slots(db, doctor_id, day)}


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut, summary="Get an appointment")
def get_appointment(
    appointment_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found.")
    return appointment


@router.post(
    "/appointments/{appointment_id}/cancel", response_model=AppointmentOut, summary="Cancel an appointment"
)
def cancel(
    appointment_id: int,
    db: Session = Depends(get_db),
    gateway: NotificationGateway = Depends(get_gateway),
    _user: User = Depends(require_role(*BOOKING_ROLES)),
) -> Appointment:
    try:
        return cancel_appointment(db, gateway, appointment_id)
    except AppointmentChangeError as exc:
        raise _http_error(exc) from None


@router.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=AppointmentOut,
    summary="Reschedule an appointment",
)
def reschedule(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    gateway: NotificationGateway = Depends(get_gateway),
    _user: User = Depends(require_role(*BOOKING_ROLES)),
) -> Appointment:
    try:
        return reschedule_appointment(db, gateway, appointment_id, payload.new_slot_start)
    except (SlotUnavailableError, AppointmentChangeError) as exc:
        raise _http_error(exc) from None
