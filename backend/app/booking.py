from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .appointments import (
    SLOT_UNAVAILABLE_MESSAGE,
    AppointmentChangeError,
    SlotUnavailableError,
    book_appointment,
    to_utc_naive,
)
from .database import get_db
from .doctors import get_doctor_or_404, is_schedule_slot
from .models import Appointment, AuditLogEntry, Patient, User
from .notifications import NotificationGateway, get_gateway
from .rbac import require_role
from .roles import PATIENT, RECEPTIONIST
from .schemas import AppointmentOut, OpdBookingRequest

router = APIRouter(tags=["Appointments"])

# HMS-F-005: a patient or receptionist books OPD appointments.
BOOKING_ROLES = (RECEPTIONIST, PATIENT)


@router.post(
    "/appointments/opd",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book an OPD appointment",
)
def book_opd_appointment(
    payload: OpdBookingRequest,
    db: Session = Depends(get_db),
    gateway: NotificationGateway = Depends(get_gateway),
    user: User = Depends(require_role(*BOOKING_ROLES)),
) -> Appointment:
    """US-08: book an OPD appointment for a registered patient with a chosen doctor and slot.

    Validates the request against real data (registered patient, active doctor, department,
    doctor's schedule) and then hands off to the US-09 `book_appointment()` service, which enforces
    no double-booking and sends the US-11 confirmation/reminder.
    """
    patient = db.query(Patient).filter(Patient.uhid == payload.patient_uhid.strip()).one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found. Register the patient first.")

    doctor = get_doctor_or_404(db, payload.doctor_id.strip())
    if not doctor.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "This doctor is not currently taking appointments.")
    if payload.department and payload.department.strip().lower() != doctor.department.lower():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Doctor does not belong to the chosen department.")

    # AC-HMS-F-005: booking succeeds only for an available slot, i.e. one the doctor's schedule offers.
    slot_start = to_utc_naive(payload.slot_start)
    if not is_schedule_slot(db, doctor, slot_start):
        raise HTTPException(status.HTTP_409_CONFLICT, SLOT_UNAVAILABLE_MESSAGE)

    try:
        appointment = book_appointment(db, gateway, patient.uhid, doctor.doctor_id, slot_start)
    except SlotUnavailableError:
        raise HTTPException(status.HTTP_409_CONFLICT, SLOT_UNAVAILABLE_MESSAGE) from None
    except AppointmentChangeError as exc:
        raise HTTPException(exc.status_code, exc.message) from None

    db.add(
        AuditLogEntry(
            event_type="APPOINTMENT_BOOKED",
            username=user.username,
            detail=f"Appointment {appointment.id}: {patient.uhid} with {doctor.doctor_id} at {slot_start:%Y-%m-%d %H:%M} UTC",
        )
    )
    db.commit()
    return appointment
