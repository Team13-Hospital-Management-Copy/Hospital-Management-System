from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, Consultation, Prescription
from .rbac import require_role
from .roles import DOCTOR, PHARMACIST
from .schemas import PrescriptionCreate, PrescriptionOut

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


@router.post(
    "",
    response_model=PrescriptionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prescription(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(DOCTOR)),
):
    consultation = db.get(Consultation, payload.consultation_id)

    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation not found.",
        )

    prescription = Prescription(
        patient_uhid=consultation.patient_uhid,
        consultation_id=consultation.id,
        doctor_username=current_user.username,
        drug_name=payload.drug_name.strip(),
        dosage=payload.dosage.strip(),
        frequency=payload.frequency.strip(),
        duration=payload.duration.strip(),
    )

    if not all(
        [
            prescription.drug_name,
            prescription.dosage,
            prescription.frequency,
            prescription.duration,
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Drug name, dosage, frequency, and duration cannot be blank.",
        )

    db.add(prescription)
    db.flush()

    db.add(
        AuditLogEntry(
            event_type="PRESCRIPTION_CREATED",
            username=current_user.username,
            detail=(
                f"prescription_id={prescription.id}, "
                f"consultation_id={consultation.id}, "
                f"patient_uhid={consultation.patient_uhid}"
            ),
        )
    )

    db.commit()
    db.refresh(prescription)

    return prescription


@router.get(
    "/{patient_uhid}",
    response_model=list[PrescriptionOut],
)
def get_patient_prescriptions(
    patient_uhid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(PHARMACIST)),
):
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_uhid == patient_uhid)
        .order_by(Prescription.created_at.desc())
        .all()
    )

    db.add(
        AuditLogEntry(
            event_type="PRESCRIPTIONS_VIEWED",
            username=current_user.username,
            detail=f"patient_uhid={patient_uhid}, count={len(prescriptions)}",
        )
    )
    db.commit()

    return prescriptions
