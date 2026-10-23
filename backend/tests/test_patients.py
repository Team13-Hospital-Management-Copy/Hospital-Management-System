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


def test_register_patient_returns_patient_and_uhid(client, db_session, receptionist_header):
    response = client.post(PATIENTS_URL, json=patient_payload(), headers=receptionist_header)

    assert response.status_code == 201
    body = response.json()
    assert body["uhid"].startswith("HMS-")
    assert body["full_name"] == "Test Patient"
    assert body["age"] == 30

    patient = db_session.query(Patient).filter_by(uhid=body["uhid"]).one()
    assert patient.phone == "9876543210"


def test_each_patient_gets_a_different_uhid(client, receptionist_header):
    first = client.post(PATIENTS_URL, json=patient_payload(), headers=receptionist_header)
    second = client.post(
        PATIENTS_URL,
        json=patient_payload(full_name="Another Patient", phone="9876543211"),
        headers=receptionist_header,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["uhid"] != second.json()["uhid"]


def test_invalid_age_is_rejected(client, receptionist_header):
    response = client.post(PATIENTS_URL, json=patient_payload(age=-1), headers=receptionist_header)

    assert response.status_code == 422


def test_registration_creates_audit_log(client, db_session, receptionist_header):
    response = client.post(PATIENTS_URL, json=patient_payload(), headers=receptionist_header)

    assert response.status_code == 201
    entry = (
        db_session.query(AuditLogEntry)
        .filter_by(event_type="PATIENT_REGISTERED")
        .one_or_none()
    )
    assert entry is not None
    assert response.json()["uhid"] in entry.detail
    assert entry.username == "receptionist1"


def test_unknown_uhid_returns_404(client, receptionist_header):
    response = client.get("/patients/HMS-999999", headers=receptionist_header)

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found."


def test_registration_requires_login(client):
    assert client.post(PATIENTS_URL, json=patient_payload()).status_code == 401


def test_registration_requires_the_receptionist_role(client, seed_user, login_token):
    from app.roles import PHARMACIST

    seed_user(username="pharm1", role=PHARMACIST)
    token = login_token("pharm1")

    response = client.post(PATIENTS_URL, json=patient_payload(), headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_lookup_by_uhid_requires_login(client):
    assert client.get("/patients/HMS-999999").status_code == 401
