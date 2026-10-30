
from datetime import datetime, timedelta

from app.models import (
    Appointment,
    Consultation,
    LabTestOrder,
    Patient,
    Prescription,
    User,
)
from app.roles import DOCTOR, RECEPTIONIST
from app.security import hash_password


def create_ehr_test_patient(db_session, uhid):
    patient = Patient(
        uhid=uhid,
        full_name="EHR Test Patient",
        age=35,
        gender="Female",
        phone="9876543210",
        address="Test Address",
    )
    db_session.add(patient)
    db_session.commit()
    return patient


def create_ehr_test_doctor(db_session, username):
    doctor = User(
        username=username,
        password_hash=hash_password("CorrectHorseBattery9!"),
        role=DOCTOR,
    )
    db_session.add(doctor)
    db_session.commit()
    return doctor


def test_doctor_can_retrieve_patient_ehr(
    client, db_session, login_token
):
    patient = create_ehr_test_patient(db_session, "HMS-EHR-001")
    create_ehr_test_doctor(db_session, "doctor_ehr_001")

    appointment = Appointment(
        patient_uhid=patient.uhid,
        doctor_id="DOC-001",
        slot_start=datetime.now() - timedelta(days=2),
        status="BOOKED",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    consultation = Consultation(
        appointment_id=appointment.id,
        patient_uhid=patient.uhid,
        diagnosis="Viral fever",
        blood_pressure="120/80",
        temperature="37.5",
        pulse=78,
        spo2=98,
        clinical_notes="Rest and fluids advised.",
    )
    db_session.add(consultation)
    db_session.commit()
    db_session.refresh(consultation)

    token = login_token("doctor_ehr_001")

    response = client.get(
        f"/patients/{patient.uhid}/ehr",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["patient"]["uhid"] == patient.uhid
    assert data["patient"]["full_name"] == "EHR Test Patient"
    assert len(data["visits"]) == 1

    visit = data["visits"][0]

    assert visit["appointment_id"] == appointment.id
    assert visit["diagnosis"] == "Viral fever"
    assert visit["blood_pressure"] == "120/80"
    assert visit["temperature"] == "37.5"
    assert visit["pulse"] == 78
    assert visit["spo2"] == 98
    assert visit["clinical_notes"] == "Rest and fluids advised."


def test_patient_ehr_visits_are_in_chronological_order(
    client, db_session, login_token
):
    patient = create_ehr_test_patient(db_session, "HMS-EHR-002")
    create_ehr_test_doctor(db_session, "doctor_ehr_002")

    visit_dates = [
        datetime.now() - timedelta(days=10),
        datetime.now() - timedelta(days=5),
        datetime.now() - timedelta(days=1),
    ]

    diagnoses = ["Initial fever", "Follow-up consultation", "Recovery review"]

    for visit_date, diagnosis in zip(visit_dates, diagnoses):
        appointment = Appointment(
            patient_uhid=patient.uhid,
            doctor_id="DOC-001",
            slot_start=visit_date,
            status="BOOKED",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        consultation = Consultation(
            appointment_id=appointment.id,
            patient_uhid=patient.uhid,
            diagnosis=diagnosis,
            clinical_notes=f"Notes for {diagnosis}",
        )
        db_session.add(consultation)
        db_session.commit()

    token = login_token("doctor_ehr_002")

    response = client.get(
        f"/patients/{patient.uhid}/ehr",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    visits = response.json()["visits"]

    assert len(visits) == 3
    assert [visit["diagnosis"] for visit in visits] == diagnoses

    returned_dates = [
        datetime.fromisoformat(visit["visit_date"])
        for visit in visits
    ]

    assert returned_dates == sorted(returned_dates)


def test_patient_ehr_includes_prescriptions_and_lab_results(
    client, db_session, login_token
):
    patient = create_ehr_test_patient(db_session, "HMS-EHR-003")
    create_ehr_test_doctor(db_session, "doctor_ehr_003")

    appointment = Appointment(
        patient_uhid=patient.uhid,
        doctor_id="DOC-001",
        slot_start=datetime.now() - timedelta(days=3),
        status="BOOKED",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    consultation = Consultation(
        appointment_id=appointment.id,
        patient_uhid=patient.uhid,
        diagnosis="Diabetes follow-up",
        clinical_notes="Monitor blood sugar levels.",
    )
    db_session.add(consultation)
    db_session.commit()
    db_session.refresh(consultation)

    prescription = Prescription(
        patient_uhid=patient.uhid,
        consultation_id=consultation.id,
        doctor_username="doctor_ehr_003",
        drug_name="Metformin",
        dosage="500 mg",
        frequency="Twice daily",
        duration="30 days",
    )

    lab_test = LabTestOrder(
        appointment_id=appointment.id,
        patient_uhid=patient.uhid,
        test_name="Blood Glucose",
        status="COMPLETED",
        ordered_by="doctor_ehr_003",
        result="Fasting glucose: 110 mg/dL",
    )

    db_session.add_all([prescription, lab_test])
    db_session.commit()

    token = login_token("doctor_ehr_003")

    response = client.get(
        f"/patients/{patient.uhid}/ehr",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    visit = response.json()["visits"][0]

    assert len(visit["prescriptions"]) == 1
    assert visit["prescriptions"][0]["drug_name"] == "Metformin"
    assert visit["prescriptions"][0]["dosage"] == "500 mg"
    assert visit["prescriptions"][0]["frequency"] == "Twice daily"

    assert len(visit["lab_tests"]) == 1
    assert visit["lab_tests"][0]["test_name"] == "Blood Glucose"
    assert visit["lab_tests"][0]["status"] == "COMPLETED"
    assert visit["lab_tests"][0]["result"] == "Fasting glucose: 110 mg/dL"


def test_patient_ehr_returns_404_for_unknown_uhid(
    client, db_session, login_token
):
    create_ehr_test_doctor(db_session, "doctor_ehr_004")
    token = login_token("doctor_ehr_004")

    response = client.get(
        "/patients/HMS-UNKNOWN/ehr",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_patient_ehr_requires_doctor_role(
    client, db_session, login_token
):
    patient = create_ehr_test_patient(db_session, "HMS-EHR-005")

    receptionist = User(
        username="receptionist_ehr_005",
        password_hash=hash_password("CorrectHorseBattery9!"),
        role=RECEPTIONIST,
    )
    db_session.add(receptionist)
    db_session.commit()

    token = login_token("receptionist_ehr_005")

    response = client.get(
        f"/patients/{patient.uhid}/ehr",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_patient_ehr_requires_authentication(client):
    response = client.get("/patients/HMS-EHR-001/ehr")

    assert response.status_code in (401, 403)
