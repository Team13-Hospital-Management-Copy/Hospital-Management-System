"""US-17 / HMS-F-014 / HMS-F-015 / HMS-F-016 / TC-Bill-01..03: consolidated billing."""

from app.models import AuditLogEntry, Patient
from app.roles import DOCTOR, RECEPTIONIST

BILLING_URL = "/billing"


def receptionist_auth(seed_user, login_token, username="receptionist_us17"):
    seed_user(username=username, role=RECEPTIONIST)
    return {"Authorization": f"Bearer {login_token(username)}"}


def seed_patient(db_session, uhid="HMS-000401"):
    patient = Patient(
        uhid=uhid, full_name="Billing Test Patient", age=45, gender="F", phone="9876500000", address=""
    )
    db_session.add(patient)
    db_session.commit()
    return patient


def open_bill(client, headers, uhid="HMS-000401"):
    return client.post(f"{BILLING_URL}/bills", headers=headers, json={"patient_uhid": uhid}).json()


def add_item(client, headers, bill_id, category="CONSULTATION", description="OPD consultation", amount="500.00"):
    return client.post(
        f"{BILLING_URL}/bills/{bill_id}/items",
        headers=headers,
        json={"category": category, "description": description, "amount": amount},
    )


def test_create_bill_requires_receptionist_role(client, db_session, seed_user, login_token):
    seed_user(username="doctor_us17", role=DOCTOR)
    seed_patient(db_session)
    headers = {"Authorization": f"Bearer {login_token('doctor_us17')}"}

    response = client.post(f"{BILLING_URL}/bills", headers=headers, json={"patient_uhid": "HMS-000401"})

    assert response.status_code == 403


def test_create_bill_for_missing_patient_returns_404(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)

    response = client.post(f"{BILLING_URL}/bills", headers=headers, json={"patient_uhid": "HMS-999999"})

    assert response.status_code == 404


def test_bill_total_equals_sum_of_line_items(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)

    add_item(client, headers, bill["id"], "CONSULTATION", "OPD consultation", "500.00")
    response = add_item(client, headers, bill["id"], "LAB", "Complete Blood Count", "250.50")

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["subtotal"] == "750.50"
    assert data["total"] == "750.50"
    assert len(data["line_items"]) == 2

    audit = db_session.query(AuditLogEntry).filter_by(event_type="BILL_ITEM_ADDED").first()
    assert audit is not None


def test_invalid_category_rejected(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)

    response = add_item(client, headers, bill["id"], category="NOT_A_CATEGORY")

    assert response.status_code == 422


def test_percent_discount_applied_before_total(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="1000.00")

    response = client.post(
        f"{BILLING_URL}/bills/{bill['id']}/discount",
        headers=headers,
        json={"discount_percent": "10.00", "reason": "Staff insurance scheme"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subtotal"] == "1000.00"
    assert data["discount_percent"] == "10.00"
    assert data["total"] == "900.00"


def test_flat_discount_cannot_exceed_subtotal(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="100.00")

    response = client.post(
        f"{BILLING_URL}/bills/{bill['id']}/discount",
        headers=headers,
        json={"discount_amount": "500.00"},
    )

    assert response.status_code == 422


def test_discount_rejects_both_percent_and_amount_together(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)

    response = client.post(
        f"{BILLING_URL}/bills/{bill['id']}/discount",
        headers=headers,
        json={"discount_percent": "10.00", "discount_amount": "5.00"},
    )

    assert response.status_code == 422


def test_payment_generates_receipt_and_bill_becomes_paid(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="500.00")

    response = client.post(
        f"{BILLING_URL}/bills/{bill['id']}/payments",
        headers=headers,
        json={"amount": "500.00", "method": "CASH"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data["payments"]) == 1
    assert data["payments"][0]["receipt_number"].startswith("RCPT-")
    assert data["amount_paid"] == "500.00"
    assert data["balance_due"] == "0.00"
    assert data["status"] == "PAID"

    audit = db_session.query(AuditLogEntry).filter_by(event_type="PAYMENT_RECORDED").first()
    assert audit is not None


def test_partial_payment_leaves_bill_open_with_balance(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="500.00")

    response = client.post(
        f"{BILLING_URL}/bills/{bill['id']}/payments",
        headers=headers,
        json={"amount": "200.00", "method": "UPI"},
    )

    data = response.json()
    assert data["status"] == "OPEN"
    assert data["balance_due"] == "300.00"


def test_invalid_payment_method_rejected(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="100.00")

    response = client.post(
        f"{BILLING_URL}/bills/{bill['id']}/payments",
        headers=headers,
        json={"amount": "100.00", "method": "CRYPTO"},
    )

    assert response.status_code == 422


def test_cannot_modify_a_paid_bill(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="100.00")
    client.post(
        f"{BILLING_URL}/bills/{bill['id']}/payments", headers=headers, json={"amount": "100.00", "method": "CASH"}
    )

    response = add_item(client, headers, bill["id"], amount="50.00")

    assert response.status_code == 409


def test_get_bill_returns_current_state(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)
    seed_patient(db_session)
    bill = open_bill(client, headers)
    add_item(client, headers, bill["id"], amount="300.00")

    response = client.get(f"{BILLING_URL}/bills/{bill['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["subtotal"] == "300.00"


def test_get_missing_bill_returns_404(client, db_session, seed_user, login_token):
    headers = receptionist_auth(seed_user, login_token)

    response = client.get(f"{BILLING_URL}/bills/999999", headers=headers)

    assert response.status_code == 404
