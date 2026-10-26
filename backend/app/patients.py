from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, Patient, User
from .rbac import require_role
from .roles import DOCTOR, RECEPTIONIST
from .schemas import PatientCreate, PatientResponse

router = APIRouter(prefix="/patients", tags=["Patients"])

# AC-HMS-F-002: searching by any of the three keys returns the matching patients.
PATIENT_SEARCH_LIMIT = 50

# A concurrent registration can compute the same "next" UHID before either commits; retry with a
# freshly generated one rather than failing the second request outright.
MAX_UHID_GENERATION_ATTEMPTS = 5


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
    summary="Register a new patient",
)
def register_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(RECEPTIONIST)),
) -> PatientResponse:
    full_name = payload.full_name.strip()
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Patient name cannot be empty.",
        )

    for _ in range(MAX_UHID_GENERATION_ATTEMPTS):
        patient = Patient(
            uhid=generate_uhid(db),
            full_name=full_name,
            age=payload.age,
            gender=payload.gender.strip(),
            phone=payload.phone.strip(),
            address=payload.address.strip(),
        )
        db.add(patient)
        try:
            db.flush()
        except IntegrityError:
            # Another concurrent registration took this UHID first; retry with a new one.
            db.rollback()
            continue

        db.add(
            AuditLogEntry(
                event_type="PATIENT_REGISTERED",
                username=user.username,
                detail=f"Registered patient {patient.uhid}",
            )
        )
        db.commit()
        db.refresh(patient)
        return patient

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Could not register patient: UHID generation is under heavy contention. Try again.",
    )


def _contains_pattern(term: str) -> str:
    """Build a LIKE pattern for a partial match, escaping LIKE wildcards in user input."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/search", response_model=list[PatientResponse], summary="Search patients")
def search_patients(
    uhid: str | None = Query(default=None, max_length=20),
    name: str | None = Query(default=None, max_length=150),
    phone: str | None = Query(default=None, max_length=20),
    db: Session = Depends(get_db),
    _user=Depends(require_role(RECEPTIONIST, DOCTOR)),
) -> list[Patient]:
    keys = {"uhid": uhid, "name": name, "phone": phone}
    provided = {field: value for field, value in keys.items() if value is not None}

    if len(provided) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of uhid, name or phone.",
        )

    field, value = next(iter(provided.items()))
    value = value.strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search value cannot be empty.",
        )

    column = {"uhid": Patient.uhid, "name": Patient.full_name, "phone": Patient.phone}[field]
    return (
        db.query(Patient)
        .filter(column.ilike(_contains_pattern(value), escape="\\"))
        .order_by(Patient.uhid)
        .limit(PATIENT_SEARCH_LIMIT)
        .all()
    )


@router.get("/{uhid}", response_model=PatientResponse, summary="Get patient by UHID")
def get_patient_by_uhid(
    uhid: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role(RECEPTIONIST, DOCTOR)),
) -> PatientResponse:
    patient = db.query(Patient).filter(Patient.uhid == uhid).first()

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    return patient
