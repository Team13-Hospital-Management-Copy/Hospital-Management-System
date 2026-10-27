from datetime import datetime, timedelta

from app.models import Appointment, Consultation, Patient, User
from app.roles import DOCTOR, RECEPTIONIST
from app.security import hash_password
from datetime import datetime, timedelta


from app.roles import DOCTOR, RECEPTIONIST
from app.security import hash_password


def test_consultation_requires_doctor_role(client, db_session, login_token):
    doctor = User(
        username="doctor_us12",
        password_hash=hash_password("CorrectHorseBattery9!"),
        role=DOCTOR,
    )
    receptionist = User(
        username="receptionist_us12",
        password_hash=hash_password("CorrectHorseBattery9!"),
        role=RECEPTIONIST,
    )
    db_session.add_all([doctor, receptionist])
    db_session.commit()

    doctor_token = login_token("doctor_us12")
    receptionist_token = login_token("receptionist_us12")

    response = client.post(
        "/consultations",
        headers={"Authorization": f"Bearer {receptionist_token}"},
        json={
            "appointment_id": 999,
            "diagnosis": "Test diagnosis",
        },
    )

    assert response.status_code == 403

    
def test_doctor_creates_consultation_linked_to_correct_patient(
    client, db_session, seed_user, login_token
):
    patient = Patient(
        uhid="HMS-000101",
        full_name="Test Patient",
        age=35,
        gender="Female",
        phone="9876543210",
        address="",
    )
    doctor_user = User(
        username="doctor_save_us12",
        password_hash=hash_password("CorrectHorseBattery9!"),
        role=DOCTOR,
    )
    db_session.add_all([patient, doctor_user])
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

    token = login_token("doctor_save_us12")
    response = client.post(
        "/consultations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "appointment_id": appointment.id,
            "diagnosis": "Viral fever",
            "blood_pressure": "120/80",
            "temperature": "37.5",
            "pulse": 78,
            "spo2": 98,
            "clinical_notes": "Rest and fluids advised.",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["appointment_id"] == appointment.id
    assert data["patient_uhid"] == patient.uhid
    assert data["diagnosis"] == "Viral fever"
    assert data["clinical_notes"] == "Rest and fluids advised."

    
def test_consultation_for_missing_appointment_returns_404(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_missing_us12", role=DOCTOR)
    token = login_token("doctor_missing_us12")

    response = client.post(
        "/consultations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "appointment_id": 999999,
            "diagnosis": "Test diagnosis",
        },
    )

    assert response.status_code == 404


def test_duplicate_consultation_for_appointment_returns_409(
    client, db_session, login_token
):
    patient = Patient(
        uhid="HMS-000102",
        full_name="Duplicate Test Patient",
        age=40,
        gender="Male",
        phone="9876543211",
        address="",
    )
    doctor_user = User(
        username="doctor_duplicate_us12",
        password_hash=hash_password("CorrectHorseBattery9!"),
        role=DOCTOR,
    )
    db_session.add_all([patient, doctor_user])
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

    existing = Consultation(
        appointment_id=appointment.id,
        patient_uhid=patient.uhid,
        diagnosis="Existing diagnosis",
        clinical_notes="Existing notes",
    )
    db_session.add(existing)
    db_session.commit()

    token = login_token("doctor_duplicate_us12")
    response = client.post(
        "/consultations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "appointment_id": appointment.id,
            "diagnosis": "Another diagnosis",
        },
    )

    assert response.status_code == 409


