
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    APPOINTMENT_STATUS_BOOKED,
    Appointment,
    AuditLogEntry,
    Consultation,
)
from .rbac import require_role
from .roles import DOCTOR
from .schemas import ConsultationCreate, ConsultationOut


router = APIRouter(prefix="/consultations", tags=["Consultations"])


@router.post(
    "",
    response_model=ConsultationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_consultation(
    payload: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(DOCTOR)),
):
    appointment = db.get(Appointment, payload.appointment_id)

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if appointment.status != APPOINTMENT_STATUS_BOOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consultations can only be recorded for booked appointments.",
        )

    existing = (
        db.query(Consultation)
        .filter(Consultation.appointment_id == appointment.id)
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A consultation already exists for this appointment.",
        )

    diagnosis = payload.diagnosis.strip()
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Diagnosis cannot be blank.",
        )

    consultation = Consultation(
        appointment_id=appointment.id,
        patient_uhid=appointment.patient_uhid,
        diagnosis=diagnosis,
        blood_pressure=payload.blood_pressure,
        temperature=payload.temperature,
        pulse=payload.pulse,
        spo2=payload.spo2,
        clinical_notes=payload.clinical_notes,
    )

    db.add(consultation)
    db.flush()

    db.add(
        AuditLogEntry(
            event_type="CONSULTATION_CREATED",
            username=current_user.username,
            detail=(
                f"consultation_id={consultation.id}, "
                f"appointment_id={appointment.id}, "
                f"patient_uhid={appointment.patient_uhid}"
            ),
        )
    )

    db.commit()
    db.refresh(consultation)

    return consultation
