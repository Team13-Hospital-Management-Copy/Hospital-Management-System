from datetime import datetime, timedelta

from app.models import (
    Appointment,
    AuditLogEntry,
    Consultation,
    Patient,
    Prescription,
    User,
)
from app.roles import DOCTOR, PHARMACIST, RECEPTIONIST
from app.security import hash_password


def create_patient_and_consultation(db_session, uhid="HMS-000201"):
    patient = Patient(
        uhid=uhid,
        full_name="Prescription Test Patient",
        age=35,
        gender="Female",
        phone="9876543210",
        address="",
    )

    db_session.add(patient)
    db_session.commit()

    appointment = Appointment(
        patient_uhid=patient.uhid,
        doctor_id="DOC-001",
        slot_start=datetime.now() + timedelta(days=1),
        status="BOOKED",
    )

    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    consultation = Consultation(
        appointment_id=appointment.id,
        patient_uhid=patient.uhid,
        diagnosis="Viral fever",
        clinical_notes="Rest and fluids advised.",
    )

    db_session.add(consultation)
    db_session.commit()
    db_session.refresh(consultation)

    return patient, consultation


def test_doctor_creates_prescription_and_audit_log(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_us13", role=DOCTOR)
    patient, consultation = create_patient_and_consultation(db_session)

    token = login_token("doctor_us13")

    response = client.post(
        "/prescriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "consultation_id": consultation.id,
            "drug_name": "Paracetamol",
            "dosage": "500 mg",
            "frequency": "Twice daily",
            "duration": "5 days",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["patient_uhid"] == patient.uhid
    assert data["consultation_id"] == consultation.id
    assert data["doctor_username"] == "doctor_us13"
    assert data["drug_name"] == "Paracetamol"
    assert data["dosage"] == "500 mg"
    assert data["frequency"] == "Twice daily"
    assert data["duration"] == "5 days"

    audit = (
        db_session.query(AuditLogEntry)
        .filter_by(event_type="PRESCRIPTION_CREATED")
        .first()
    )
    assert audit is not None
    assert audit.username == "doctor_us13"


def test_pharmacist_views_prescriptions_for_correct_uhid(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_us13_view", role=DOCTOR)
    seed_user(username="pharmacist_us13", role=PHARMACIST)

    patient, consultation = create_patient_and_consultation(db_session)

    prescription = Prescription(
        patient_uhid=patient.uhid,
        consultation_id=consultation.id,
        doctor_username="doctor_us13_view",
        drug_name="Paracetamol",
        dosage="500 mg",
        frequency="Twice daily",
        duration="5 days",
    )
    db_session.add(prescription)
    db_session.commit()

    token = login_token("pharmacist_us13")

    response = client.get(
        f"/prescriptions/{patient.uhid}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["patient_uhid"] == patient.uhid
    assert data[0]["drug_name"] == "Paracetamol"

    audit = (
        db_session.query(AuditLogEntry)
        .filter_by(event_type="PRESCRIPTIONS_VIEWED")
        .first()
    )
    assert audit is not None
    assert audit.username == "pharmacist_us13"


def test_receptionist_cannot_create_prescription(
    client, db_session, seed_user, login_token
):
    seed_user(username="receptionist_us13", role=RECEPTIONIST)
    _, consultation = create_patient_and_consultation(db_session)

    token = login_token("receptionist_us13")

    response = client.post(
        "/prescriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "consultation_id": consultation.id,
            "drug_name": "Paracetamol",
            "dosage": "500 mg",
            "frequency": "Twice daily",
            "duration": "5 days",
        },
    )

    assert response.status_code == 403


def test_doctor_cannot_view_prescriptions(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_us13_read", role=DOCTOR)
    token = login_token("doctor_us13_read")

    response = client.get(
        "/prescriptions/HMS-000201",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_missing_consultation_returns_404(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_us13_missing", role=DOCTOR)
    token = login_token("doctor_us13_missing")

    response = client.post(
        "/prescriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "consultation_id": 999999,
            "drug_name": "Paracetamol",
            "dosage": "500 mg",
            "frequency": "Twice daily",
            "duration": "5 days",
        },
    )

    assert response.status_code == 404