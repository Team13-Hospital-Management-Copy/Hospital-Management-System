
from app.models import AuditLogEntry, Patient

PATIENTS_URL = "/patients/"


def patient_payload(**overrides):
    data = {
        "full_name": "Test Patient",
        "age": 30,
        "gender": "Female",
        "phone": "9876543210",
        "address": "Test Address",
    }
    data.update(overrides)
    return data


def test_register_patient_returns_patient_and_uhid(client, db_session):
    response = client.post(PATIENTS_URL, json=patient_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["uhid"].startswith("HMS-")
    assert body["full_name"] == "Test Patient"
    assert body["age"] == 30

    patient = db_session.query(Patient).filter_by(uhid=body["uhid"]).one()
    assert patient.phone == "9876543210"


def test_each_patient_gets_a_different_uhid(client):
    first = client.post(PATIENTS_URL, json=patient_payload())
    second = client.post(
        PATIENTS_URL,
        json=patient_payload(full_name="Another Patient", phone="9876543211"),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["uhid"] != second.json()["uhid"]


def test_invalid_age_is_rejected(client):
    response = client.post(PATIENTS_URL, json=patient_payload(age=-1))

    assert response.status_code == 422



def test_registration_creates_audit_log(client, db_session):
    response = client.post(PATIENTS_URL, json=patient_payload())

    assert response.status_code == 201
    entry = (
        db_session.query(AuditLogEntry)
        .filter_by(event_type="PATIENT_REGISTERED")
        .one_or_none()
    )
    assert entry is not None
    assert response.json()["uhid"] in entry.detail


def test_unknown_uhid_returns_404(client):
    response = client.get("/patients/HMS-999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found."

