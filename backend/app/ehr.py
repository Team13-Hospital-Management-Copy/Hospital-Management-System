
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLogEntry, Appointment, Consultation, LabTestOrder, Patient, Prescription
from .rbac import require_role
from .roles import DOCTOR
from .schemas import (
    EHRLabTestOut,
    EHRPrescriptionOut,
    EHRVisitOut,
    PatientEHRResponse,
    PatientResponse,
)

router = APIRouter(prefix="/patients", tags=["Patient EHR"])


@router.get(
    "/{uhid}/ehr",
    response_model=PatientEHRResponse,
    summary="Retrieve a patient's longitudinal electronic health record",
)
def get_patient_ehr(
    uhid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(DOCTOR)),
):
    """
    Retrieve a patient's consultation history, prescriptions and lab results.

    Visits are returned in chronological order using the appointment date.
    Access is restricted to doctors.
    """

    patient = db.query(Patient).filter(Patient.uhid == uhid).first()

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    consultation_records = (
        db.query(Consultation, Appointment)
        .join(
            Appointment,
            Consultation.appointment_id == Appointment.id,
        )
        .filter(Consultation.patient_uhid == uhid)
        .order_by(Appointment.slot_start.asc(), Appointment.id.asc())
        .all()
    )

    visits = []

    for consultation, appointment in consultation_records:
        prescription_records = (
            db.query(Prescription)
            .filter(
                Prescription.consultation_id == consultation.id,
                Prescription.patient_uhid == uhid,
            )
            .order_by(Prescription.created_at.asc(), Prescription.id.asc())
            .all()
        )

        lab_test_records = (
            db.query(LabTestOrder)
            .filter(
                LabTestOrder.appointment_id == appointment.id,
                LabTestOrder.patient_uhid == uhid,
            )
            .order_by(LabTestOrder.ordered_at.asc(), LabTestOrder.id.asc())
            .all()
        )

        visits.append(
            EHRVisitOut(
                appointment_id=appointment.id,
                visit_date=appointment.slot_start,
                doctor_id=appointment.doctor_id,
                diagnosis=consultation.diagnosis,
                blood_pressure=consultation.blood_pressure,
                temperature=consultation.temperature,
                pulse=consultation.pulse,
                spo2=consultation.spo2,
                clinical_notes=consultation.clinical_notes,
                prescriptions=[
                    EHRPrescriptionOut.model_validate(item)
                    for item in prescription_records
                ],
                lab_tests=[
                    EHRLabTestOut.model_validate(item)
                    for item in lab_test_records
                ],
            )
        )

    patient_response = PatientResponse(
        id=patient.id,
        uhid=patient.uhid,
        full_name=patient.full_name,
        age=patient.age,
        gender=patient.gender,
        phone=patient.phone,
        address=patient.address,
    )

    # AC-HMS-SR-004 / US-21 verification: every read of an EHR record is audit-logged, not
    # just writes - this endpoint previously wasn't (found during the US-21 NFR pass).
    db.add(
        AuditLogEntry(
            event_type="EHR_VIEWED",
            username=current_user.username,
            detail=f"patient_uhid={uhid}, visits={len(visits)}",
        )
    )
    db.commit()

    return PatientEHRResponse(
        patient=patient_response,
        visits=visits,
    )
