
from datetime import date, timedelta

from app.models import MedicineBatch, Patient
from app.roles import PHARMACIST


def pharmacist_auth(seed_user, login_token):
    seed_user(username="pharmacist1", role=PHARMACIST)
    return {"Authorization": f"Bearer {login_token('pharmacist1')}"}


def create_batch(client, headers, **overrides):
    payload = {
        "medicine_name": "Paracetamol",
        "batch_number": "BATCH-001",
        "quantity": 100,
        "low_stock_threshold": 10,
        "expiry_date": (date.today() + timedelta(days=60)).isoformat(),
    }
    payload.update(overrides)

    return client.post(
        "/pharmacy/batches",
        json=payload,
        headers=headers,
    )


def get_or_create_patient(db_session):
    patient = db_session.query(Patient).first()
    if patient is not None:
        return patient

    patient = Patient(
        uhid="HMS-PHARM-0001",
        full_name="Pharmacy Test Patient",
        age=30,
        gender="Other",
        phone="9999999999",
        address="Test Address",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_pharmacist_can_create_and_list_batches(
    client, seed_user, login_token
):
    headers = pharmacist_auth(seed_user, login_token)

    response = create_batch(client, headers)
    assert response.status_code == 201, response.text

    listing = client.get("/pharmacy/batches", headers=headers)
    assert listing.status_code == 200, listing.text
    assert any(
        batch["medicine_name"] == "Paracetamol"
        for batch in listing.json()
    )


def test_dispensing_decreases_stock(
    client, seed_user, login_token, db_session
):
    headers = pharmacist_auth(seed_user, login_token)
    patient = get_or_create_patient(db_session)

    created = create_batch(client, headers)
    assert created.status_code == 201, created.text
    batch = created.json()

    response = client.post(
        "/pharmacy/dispense",
        headers=headers,
        json={
            "batch_id": batch["id"],
            "patient_uhid": patient.uhid,
            "quantity": 5,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["batch"]["quantity"] == 95
    assert response.json()["dispensed_quantity"] == 5


def test_cannot_dispense_expired_batch(
    client, seed_user, login_token, db_session
):
    headers = pharmacist_auth(seed_user, login_token)
    patient = get_or_create_patient(db_session)

    created = create_batch(
        client,
        headers,
        batch_number="EXPIRED-001",
        expiry_date=(date.today() - timedelta(days=1)).isoformat(),
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/pharmacy/dispense",
        headers=headers,
        json={
            "batch_id": created.json()["id"],
            "patient_uhid": patient.uhid,
            "quantity": 1,
        },
    )

    assert response.status_code == 409, response.text
    assert "expired" in response.json()["detail"].lower()


def test_cannot_dispense_more_than_available_stock(
    client, seed_user, login_token, db_session
):
    headers = pharmacist_auth(seed_user, login_token)
    patient = get_or_create_patient(db_session)

    created = create_batch(
        client,
        headers,
        batch_number="LOW-001",
        quantity=2,
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/pharmacy/dispense",
        headers=headers,
        json={
            "batch_id": created.json()["id"],
            "patient_uhid": patient.uhid,
            "quantity": 3,
        },
    )

    assert response.status_code == 409, response.text
    assert "stock" in response.json()["detail"].lower()


def test_low_stock_alert_includes_batch(
    client, seed_user, login_token
):
    headers = pharmacist_auth(seed_user, login_token)

    response = create_batch(
        client,
        headers,
        batch_number="LOW-ALERT-001",
        quantity=3,
        low_stock_threshold=10,
    )
    assert response.status_code == 201, response.text

    alerts = client.get("/pharmacy/low-stock", headers=headers)
    assert alerts.status_code == 200, alerts.text
    assert any(
        batch["batch_number"] == "LOW-ALERT-001"
        for batch in alerts.json()
    )


def test_expiry_alert_includes_soon_expiring_batch(
    client, seed_user, login_token
):
    headers = pharmacist_auth(seed_user, login_token)

    response = create_batch(
        client,
        headers,
        batch_number="EXPIRY-ALERT-001",
        expiry_date=(date.today() + timedelta(days=7)).isoformat(),
    )
    assert response.status_code == 201, response.text

    alerts = client.get(
        "/pharmacy/expiry-alerts?within_days=30",
        headers=headers,
    )
    assert alerts.status_code == 200, alerts.text

    matching_batch = next(
        (
            batch
            for batch in alerts.json()
            if batch["batch_number"] == "EXPIRY-ALERT-001"
        ),
        None,
    )
    assert matching_batch is not None
    assert matching_batch["days_until_expiry"] == 7


def test_pharmacy_requires_authentication(client):
    response = client.get("/pharmacy/batches")
    assert response.status_code == 401
