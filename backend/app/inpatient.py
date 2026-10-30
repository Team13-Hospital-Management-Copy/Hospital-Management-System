from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from html import escape
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Admission, AuditLogEntry, Bed, Patient
from .rbac import require_role
from .roles import ADMINISTRATOR, RECEPTIONIST, SYSTEM_ADMINISTRATOR


router = APIRouter(prefix="/inpatient", tags=["Inpatient"])


STAFF_ROLES = (RECEPTIONIST, ADMINISTRATOR, SYSTEM_ADMINISTRATOR)


class BedCreate(BaseModel):
    bed_number: str = Field(min_length=1, max_length=30)
    ward: str = Field(min_length=1, max_length=100)


class BedOut(BaseModel):
    id: int
    bed_number: str
    ward: str
    is_active: bool
    occupied: bool


class AdmissionCreate(BaseModel):
    patient_uhid: str = Field(min_length=1, max_length=20)
    bed_id: int = Field(gt=0)
    diagnosis: str = Field(default="", max_length=500)
    treatment: str = Field(default="", max_length=2000)
    follow_up_instructions: str = Field(default="", max_length=2000)


class AdmissionOut(BaseModel):
    id: int
    patient_uhid: str
    bed_id: int
    admitted_at: datetime
    discharged_at: datetime | None
    diagnosis: str
    treatment: str
    follow_up_instructions: str


class DischargeSummaryOut(BaseModel):
    admission_id: int
    patient_uhid: str
    patient_name: str
    bed_number: str
    ward: str
    admitted_at: datetime
    discharged_at: datetime
    diagnosis: str
    treatment: str
    follow_up_instructions: str


@router.post("/beds", response_model=BedOut, status_code=status.HTTP_201_CREATED)
def create_bed(
    payload: BedCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*STAFF_ROLES)),
):
    bed_number = payload.bed_number.strip()
    ward = payload.ward.strip()

    if not bed_number or not ward:
        raise HTTPException(status_code=422, detail="Bed number and ward are required.")

    if db.query(Bed).filter(Bed.bed_number == bed_number).first():
        raise HTTPException(status_code=409, detail="Bed number already exists.")

    bed = Bed(bed_number=bed_number, ward=ward)
    db.add(bed)
    db.add(
        AuditLogEntry(
            event_type="BED_CREATED",
            username=user.username,
            detail=f"Created bed {bed_number} in ward {ward}",
        )
    )

    try:
        db.commit()
        db.refresh(bed)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bed number already exists.")

    return BedOut(
        id=bed.id,
        bed_number=bed.bed_number,
        ward=bed.ward,
        is_active=bed.is_active,
        occupied=False,
    )


@router.get("/beds", response_model=list[BedOut])
def list_beds(
    available_only: bool = False,
    db: Session = Depends(get_db),
    _user=Depends(require_role(*STAFF_ROLES)),
):
    beds = db.query(Bed).filter(Bed.is_active.is_(True)).order_by(Bed.bed_number).all()
    results = []

    for bed in beds:
        occupied = (
            db.query(Admission)
            .filter(
                Admission.bed_id == bed.id,
                Admission.discharged_at.is_(None),
            )
            .first()
            is not None
        )

        if available_only and occupied:
            continue

        results.append(
            BedOut(
                id=bed.id,
                bed_number=bed.bed_number,
                ward=bed.ward,
                is_active=bed.is_active,
                occupied=occupied,
            )
        )

    return results


@router.post("/admissions", response_model=AdmissionOut, status_code=status.HTTP_201_CREATED)
def admit_patient(
    payload: AdmissionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*STAFF_ROLES)),
):
    patient = db.query(Patient).filter(Patient.uhid == payload.patient_uhid.strip()).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    bed = db.get(Bed, payload.bed_id)
    if bed is None or not bed.is_active:
        raise HTTPException(status_code=404, detail="Active bed not found.")

    existing_admission = (
        db.query(Admission)
        .filter(
            Admission.bed_id == bed.id,
            Admission.discharged_at.is_(None),
        )
        .first()
    )
    if existing_admission is not None:
        raise HTTPException(status_code=409, detail="Bed is already occupied.")

    admission = Admission(
        patient_uhid=patient.uhid,
        bed_id=bed.id,
        diagnosis=payload.diagnosis.strip(),
        treatment=payload.treatment.strip(),
        follow_up_instructions=payload.follow_up_instructions.strip(),
    )
    db.add(admission)
    db.add(
        AuditLogEntry(
            event_type="PATIENT_ADMITTED",
            username=user.username,
            detail=f"Patient {patient.uhid} admitted to bed {bed.bed_number}",
        )
    )

    try:
        db.commit()
        db.refresh(admission)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bed is already occupied.")

    return admission


@router.post("/admissions/{admission_id}/discharge", response_model=DischargeSummaryOut)
def discharge_patient(
    admission_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(*STAFF_ROLES)),
):
    admission = db.get(Admission, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found.")

    if admission.discharged_at is not None:
        raise HTTPException(status_code=409, detail="Patient has already been discharged.")

    patient = db.query(Patient).filter(Patient.uhid == admission.patient_uhid).first()
    bed = db.get(Bed, admission.bed_id)

    if patient is None or bed is None:
        raise HTTPException(status_code=500, detail="Admission data is incomplete.")

    admission.discharged_at = datetime.now(timezone.utc)
    db.add(
        AuditLogEntry(
            event_type="PATIENT_DISCHARGED",
            username=user.username,
            detail=f"Patient {patient.uhid} discharged from bed {bed.bed_number}",
        )
    )
    db.commit()
    db.refresh(admission)

    return DischargeSummaryOut(
        admission_id=admission.id,
        patient_uhid=patient.uhid,
        patient_name=patient.full_name,
        bed_number=bed.bed_number,
        ward=bed.ward,
        admitted_at=admission.admitted_at,
        discharged_at=admission.discharged_at,
        diagnosis=admission.diagnosis,
        treatment=admission.treatment,
        follow_up_instructions=admission.follow_up_instructions,
    )
@router.get(
    "/admissions/{admission_id}/discharge-summary/print",
    response_class=HTMLResponse,
)
def print_discharge_summary(
    admission_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role(*STAFF_ROLES)),
):
    admission = db.get(Admission, admission_id)

    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found.")

    if admission.discharged_at is None:
        raise HTTPException(
            status_code=409,
            detail="Discharge must be confirmed before printing the summary.",
        )

    patient = db.query(Patient).filter(
        Patient.uhid == admission.patient_uhid
    ).first()
    bed = db.get(Bed, admission.bed_id)

    if patient is None or bed is None:
        raise HTTPException(status_code=500, detail="Admission data is incomplete.")

    def safe(value):
        return escape(str(value or ""))

    admitted_at = safe(admission.admitted_at)
    discharged_at = safe(admission.discharged_at)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Patient Discharge Summary</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 24px;
            color: #222;
        }}
        h1, h2 {{ text-align: center; }}
        .details {{ margin: 24px 0; }}
        .field {{ margin: 14px 0; }}
        .label {{ font-weight: bold; }}
        .print-button {{
            display: block;
            margin: 24px auto;
            padding: 10px 20px;
            cursor: pointer;
        }}
        @media print {{
            body {{ margin: 0; padding: 10px; }}
            .print-button {{ display: none; }}
        }}
    </style>
</head>
<body>
    <h1>Hospital Management System</h1>
    <h2>Patient Discharge Summary</h2>

    <div class="details">
        <div class="field"><span class="label">Patient name:</span>
            {safe(patient.full_name)}</div>
        <div class="field"><span class="label">Patient UHID:</span>
            {safe(patient.uhid)}</div>
        <div class="field"><span class="label">Admission ID:</span>
            {admission.id}</div>
        <div class="field"><span class="label">Ward:</span>
            {safe(bed.ward)}</div>
        <div class="field"><span class="label">Bed number:</span>
            {safe(bed.bed_number)}</div>
        <div class="field"><span class="label">Admitted at:</span>
            {admitted_at}</div>
        <div class="field"><span class="label">Discharged at:</span>
            {discharged_at}</div>
    </div>

    <hr>

    <h3>Diagnosis</h3>
    <p>{safe(admission.diagnosis) or "Not recorded"}</p>

    <h3>Treatment</h3>
    <p>{safe(admission.treatment) or "Not recorded"}</p>

    <h3>Follow-up Instructions</h3>
    <p>{safe(admission.follow_up_instructions) or "Not recorded"}</p>

    <button class="print-button" onclick="window.print()">
        Print / Save as PDF
    </button>
</body>
</html>"""

    return HTMLResponse(content=html)