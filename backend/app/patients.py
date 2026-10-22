
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, Patient
from .schemas import PatientCreate, PatientResponse

router = APIRouter(prefix="/patients", tags=["Patients"])


def generate_uhid(db: Session) -> str:
    """Generate a unique patient identifier."""
    last_patient = (
        db.query(Patient)
        .order_by(Patient.id.desc())
        .first()
    )
    next_id = 1 if last_patient is None else last_patient.id + 1
    return f"HMS-{next_id:06d}"


@router.post(
    "/",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
) -> PatientResponse:
    patient = Patient(
        uhid=generate_uhid(db),
        full_name=payload.full_name.strip(),
        age=payload.age,
        gender=payload.gender.strip(),
        phone=payload.phone.strip(),
        address=payload.address.strip(),
    )

    if not patient.full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Patient name cannot be empty.",
        )

    try:
        db.add(patient)
        db.flush()

        db.add(
            AuditLogEntry(
                event_type="PATIENT_REGISTERED",
                username="system",
                detail=f"Registered patient {patient.uhid}",
            )
        )
        db.commit()
        db.refresh(patient)
        return patient
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not register patient due to a duplicate identifier.",
        )
    
@router.get("/{uhid}", response_model=PatientResponse)
def get_patient_by_uhid(
    uhid: str,
    db: Session = Depends(get_db),
) -> PatientResponse:
    patient = db.query(Patient).filter(Patient.uhid == uhid).first()

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    return patient


    



