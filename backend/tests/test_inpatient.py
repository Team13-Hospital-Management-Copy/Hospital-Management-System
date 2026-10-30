import time

from app.models import Admission, Bed, Patient


def create_test_patient(db_session, uhid, name):
    patient = Patient(
        uhid=uhid,
        full_name=name,
        age=35,
        gender="Female",
        phone="9876543210",
        address="Test address",
    )
    db_session.add(patient)
    db_session.commit()
    return patient


def create_test_bed(client, headers, bed_number="B-101"):
    response = client.post(
        "/inpatient/beds",
        headers=headers,
        json={
            "bed_number": bed_number,
            "ward": "General Ward",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_staff_can_create_bed(client, receptionist_header):
    bed = create_test_bed(client, receptionist_header)

    assert bed["bed_number"] == "B-101"
    assert bed["ward"] == "General Ward"
    assert bed["occupied"] is False


def test_duplicate_bed_number_is_rejected(client, receptionist_header):
    create_test_bed(client, receptionist_header)

    response = client.post(
        "/inpatient/beds",
        headers=receptionist_header,
        json={
            "bed_number": "B-101",
            "ward": "General Ward",
        },
    )

    assert response.status_code == 409


def test_patient_can_be_admitted_to_available_bed(
    client, db_session, receptionist_header
):
    patient = create_test_patient(
        db_session, "HMS-US16-001", "Admission Test Patient"
    )
    bed = create_test_bed(client, receptionist_header)

    response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient.uhid,
            "bed_id": bed["id"],
            "diagnosis": "Viral fever",
            "treatment": "Fluids and rest",
            "follow_up_instructions": "Follow up in one week",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["patient_uhid"] == patient.uhid
    assert data["bed_id"] == bed["id"]
    assert data["diagnosis"] == "Viral fever"


def test_occupied_bed_cannot_be_assigned_to_second_patient(
    client, db_session, receptionist_header
):
    patient1 = create_test_patient(
        db_session, "HMS-US16-002", "First Patient"
    )
    patient2 = create_test_patient(
        db_session, "HMS-US16-003", "Second Patient"
    )
    bed = create_test_bed(client, receptionist_header)

    first_response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient1.uhid,
            "bed_id": bed["id"],
            "diagnosis": "First diagnosis",
        },
    )
    assert first_response.status_code == 201, first_response.text

    second_response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient2.uhid,
            "bed_id": bed["id"],
            "diagnosis": "Second diagnosis",
        },
    )

    assert second_response.status_code == 409
    assert "occupied" in second_response.json()["detail"].lower()


def test_discharge_generates_summary_and_releases_bed(
    client, db_session, receptionist_header
):
    patient = create_test_patient(
        db_session, "HMS-US16-004", "Discharge Test Patient"
    )
    bed = create_test_bed(client, receptionist_header)

    admission_response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient.uhid,
            "bed_id": bed["id"],
            "diagnosis": "Viral fever",
            "treatment": "Fluids and rest",
            "follow_up_instructions": "Return in seven days",
        },
    )
    assert admission_response.status_code == 201, admission_response.text
    admission_id = admission_response.json()["id"]

    discharge_response = client.post(
        f"/inpatient/admissions/{admission_id}/discharge",
        headers=receptionist_header,
    )

    assert discharge_response.status_code == 200, discharge_response.text
    summary = discharge_response.json()

    assert summary["patient_uhid"] == patient.uhid
    assert summary["patient_name"] == patient.full_name
    assert summary["bed_number"] == bed["bed_number"]
    assert summary["diagnosis"] == "Viral fever"
    assert summary["treatment"] == "Fluids and rest"
    assert summary["follow_up_instructions"] == "Return in seven days"
    assert summary["discharged_at"] is not None

    # Once discharged, the bed should be available again.
    beds_response = client.get(
        "/inpatient/beds?available_only=true",
        headers=receptionist_header,
    )
    assert beds_response.status_code == 200
    available_bed_ids = [item["id"] for item in beds_response.json()]
    assert bed["id"] in available_bed_ids


def test_patient_cannot_be_admitted_to_missing_bed(
    client, db_session, receptionist_header
):
    patient = create_test_patient(
        db_session, "HMS-US16-005", "Missing Bed Patient"
    )

    response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient.uhid,
            "bed_id": 999999,
            "diagnosis": "Test diagnosis",
        },
    )

    assert response.status_code == 404


def test_discharge_cannot_be_confirmed_twice(
    client, db_session, receptionist_header
):
    patient = create_test_patient(
        db_session, "HMS-US16-006", "Repeated Discharge Patient"
    )
    bed = create_test_bed(client, receptionist_header)

    admission_response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient.uhid,
            "bed_id": bed["id"],
            "diagnosis": "Test diagnosis",
        },
    )
    assert admission_response.status_code == 201, admission_response.text
    admission_id = admission_response.json()["id"]

    first_discharge = client.post(
        f"/inpatient/admissions/{admission_id}/discharge",
        headers=receptionist_header,
    )
    assert first_discharge.status_code == 200, first_discharge.text

    second_discharge = client.post(
        f"/inpatient/admissions/{admission_id}/discharge",
        headers=receptionist_header,
    )
    assert second_discharge.status_code == 409


def test_printable_discharge_summary(
    client, db_session, receptionist_header
):
    patient = create_test_patient(
        db_session, "HMS-US16-007", "Printable Summary Patient"
    )
    bed = create_test_bed(client, receptionist_header, "B-107")

    admission_response = client.post(
        "/inpatient/admissions",
        headers=receptionist_header,
        json={
            "patient_uhid": patient.uhid,
            "bed_id": bed["id"],
            "diagnosis": "Viral fever",
            "treatment": "Fluids and rest",
            "follow_up_instructions": "Return in seven days",
        },
    )
    assert admission_response.status_code == 201, admission_response.text

    admission_id = admission_response.json()["id"]

    discharge_response = client.post(
        f"/inpatient/admissions/{admission_id}/discharge",
        headers=receptionist_header,
    )
    assert discharge_response.status_code == 200, discharge_response.text

    # Measure how quickly the printable summary endpoint responds.
    start_time = time.perf_counter()

    print_response = client.get(
        f"/inpatient/admissions/{admission_id}/discharge-summary/print",
        headers=receptionist_header,
    )

    elapsed_seconds = time.perf_counter() - start_time

    assert elapsed_seconds < 60, (
        f"Printable discharge summary took {elapsed_seconds:.2f} seconds"
    )

    assert print_response.status_code == 200
    assert "text/html" in print_response.headers["content-type"]
    assert "Patient Discharge Summary" in print_response.text
    assert "Printable Summary Patient" in print_response.text
    assert "Viral fever" in print_response.text
    assert "Fluids and rest" in print_response.text
    assert "Return in seven days" in print_response.text
    assert "window.print()" in print_response.text