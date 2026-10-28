"""US-14 / HMS-F-011 / TC-Clin-03: order a lab test and record its result."""

from datetime import datetime, timedelta

from app.models import Appointment, AuditLogEntry, Patient
from app.roles import DOCTOR, RECEPTIONIST

LAB_TESTS_URL = "/lab-tests"


def create_patient_and_appointment(db_session, uhid="HMS-000301", status="BOOKED"):
    patient = Patient(
        uhid=uhid,
        full_name="Lab Test Patient",
        age=40,
        gender="Male",
        phone="9876543210",
        address="",
    )
    db_session.add(patient)
    db_session.commit()

    appointment = Appointment(
        patient_uhid=patient.uhid,
        doctor_id="DOC-001",
        slot_start=datetime.now() + timedelta(days=1),
        status=status,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    return patient, appointment


def test_order_requires_doctor_role(client, db_session, seed_user, login_token):
    seed_user(username="receptionist_us14", role=RECEPTIONIST)
    _, appointment = create_patient_and_appointment(db_session)

    response = client.post(
        LAB_TESTS_URL,
        headers={"Authorization": f"Bearer {login_token('receptionist_us14')}"},
        json={"appointment_id": appointment.id, "test_name": "CBC"},
    )

    assert response.status_code == 403


def test_doctor_orders_lab_test_linked_to_correct_patient(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_us14", role=DOCTOR)
    patient, appointment = create_patient_and_appointment(db_session)

    response = client.post(
        LAB_TESTS_URL,
        headers={"Authorization": f"Bearer {login_token('doctor_us14')}"},
        json={"appointment_id": appointment.id, "test_name": "Complete Blood Count"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["appointment_id"] == appointment.id
    assert data["patient_uhid"] == patient.uhid
    assert data["test_name"] == "Complete Blood Count"
    assert data["status"] == "ORDERED"
    assert data["ordered_by"] == "doctor_us14"
    assert data["result"] is None
    assert data["completed_at"] is None

    audit = (
        db_session.query(AuditLogEntry).filter_by(event_type="LAB_TEST_ORDERED").first()
    )
    assert audit is not None
    assert audit.username == "doctor_us14"


def test_order_for_missing_appointment_returns_404(client, db_session, seed_user, login_token):
    seed_user(username="doctor_missing_us14", role=DOCTOR)

    response = client.post(
        LAB_TESTS_URL,
        headers={"Authorization": f"Bearer {login_token('doctor_missing_us14')}"},
        json={"appointment_id": 999999, "test_name": "CBC"},
    )

    assert response.status_code == 404


def test_order_for_non_booked_appointment_rejected(client, db_session, seed_user, login_token):
    seed_user(username="doctor_cancelled_us14", role=DOCTOR)
    _, appointment = create_patient_and_appointment(db_session, status="CANCELLED")

    response = client.post(
        LAB_TESTS_URL,
        headers={"Authorization": f"Bearer {login_token('doctor_cancelled_us14')}"},
        json={"appointment_id": appointment.id, "test_name": "CBC"},
    )

    assert response.status_code == 400


def test_blank_test_name_rejected(client, db_session, seed_user, login_token):
    seed_user(username="doctor_blank_us14", role=DOCTOR)
    _, appointment = create_patient_and_appointment(db_session)

    response = client.post(
        LAB_TESTS_URL,
        headers={"Authorization": f"Bearer {login_token('doctor_blank_us14')}"},
        json={"appointment_id": appointment.id, "test_name": "   "},
    )

    assert response.status_code == 422


def test_doctor_records_result_and_status_transitions_to_completed(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_result_us14", role=DOCTOR)
    _, appointment = create_patient_and_appointment(db_session)
    headers = {"Authorization": f"Bearer {login_token('doctor_result_us14')}"}

    order = client.post(
        LAB_TESTS_URL, headers=headers, json={"appointment_id": appointment.id, "test_name": "CBC"}
    ).json()

    response = client.post(
        f"{LAB_TESTS_URL}/{order['id']}/result",
        headers=headers,
        json={"result": "Hemoglobin 13.5 g/dL, WBC within normal range."},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["result"] == "Hemoglobin 13.5 g/dL, WBC within normal range."
    assert data["completed_at"] is not None

    audit = (
        db_session.query(AuditLogEntry)
        .filter_by(event_type="LAB_TEST_RESULT_RECORDED")
        .first()
    )
    assert audit is not None
    assert audit.username == "doctor_result_us14"


def test_recording_result_for_missing_order_returns_404(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_missing_result_us14", role=DOCTOR)

    response = client.post(
        f"{LAB_TESTS_URL}/999999/result",
        headers={"Authorization": f"Bearer {login_token('doctor_missing_result_us14')}"},
        json={"result": "Normal"},
    )

    assert response.status_code == 404


def test_recording_result_twice_is_rejected(client, db_session, seed_user, login_token):
    seed_user(username="doctor_twice_us14", role=DOCTOR)
    _, appointment = create_patient_and_appointment(db_session)
    headers = {"Authorization": f"Bearer {login_token('doctor_twice_us14')}"}

    order = client.post(
        LAB_TESTS_URL, headers=headers, json={"appointment_id": appointment.id, "test_name": "CBC"}
    ).json()
    client.post(f"{LAB_TESTS_URL}/{order['id']}/result", headers=headers, json={"result": "Normal"})

    response = client.post(
        f"{LAB_TESTS_URL}/{order['id']}/result", headers=headers, json={"result": "Updated"}
    )

    assert response.status_code == 409


def test_blank_result_rejected(client, db_session, seed_user, login_token):
    seed_user(username="doctor_blank_result_us14", role=DOCTOR)
    _, appointment = create_patient_and_appointment(db_session)
    headers = {"Authorization": f"Bearer {login_token('doctor_blank_result_us14')}"}

    order = client.post(
        LAB_TESTS_URL, headers=headers, json={"appointment_id": appointment.id, "test_name": "CBC"}
    ).json()

    response = client.post(f"{LAB_TESTS_URL}/{order['id']}/result", headers=headers, json={"result": "   "})

    assert response.status_code == 422


def test_list_patient_lab_tests_returns_both_statuses(
    client, db_session, seed_user, login_token
):
    seed_user(username="doctor_list_us14", role=DOCTOR)
    patient, appointment = create_patient_and_appointment(db_session)
    headers = {"Authorization": f"Bearer {login_token('doctor_list_us14')}"}

    first = client.post(
        LAB_TESTS_URL, headers=headers, json={"appointment_id": appointment.id, "test_name": "CBC"}
    ).json()
    client.post(
        LAB_TESTS_URL, headers=headers, json={"appointment_id": appointment.id, "test_name": "X-Ray Chest"}
    )
    client.post(f"{LAB_TESTS_URL}/{first['id']}/result", headers=headers, json={"result": "Normal"})

    response = client.get(f"{LAB_TESTS_URL}/{patient.uhid}", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 2
    statuses = {item["status"] for item in data}
    assert statuses == {"COMPLETED", "ORDERED"}

    audit = db_session.query(AuditLogEntry).filter_by(event_type="LAB_TESTS_VIEWED").first()
    assert audit is not None
    assert audit.username == "doctor_list_us14"


def test_list_requires_doctor_role(client, db_session, seed_user, login_token):
    seed_user(username="receptionist_list_us14", role=RECEPTIONIST)

    response = client.get(
        f"{LAB_TESTS_URL}/HMS-000301",
        headers={"Authorization": f"Bearer {login_token('receptionist_list_us14')}"},
    )

    assert response.status_code == 403
