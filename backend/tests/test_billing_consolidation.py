"""US-17 / HMS-F-018, HMS-F-019 / TC-Bill-01..03: consolidated bill built from the visit's records,
priced from the tariff, with configured discount schemes."""

from datetime import date, datetime, timedelta, timezone

from app.models import (
    Admission,
    Appointment,
    AuditLogEntry,
    Bed,
    Consultation,
    Doctor,
    LabTestOrder,
    MedicineBatch,
    Patient,
    PharmacyDispenseRecord,
)
from app.roles import ADMINISTRATOR, RECEPTIONIST

BILLING_URL = "/billing"
UHID = "HMS-000501"


def auth(seed_user, login_token, username, role):
    seed_user(username=username, role=role)
    return {"Authorization": f"Bearer {login_token(username)}"}


def headers_for(seed_user, login_token):
    return auth(seed_user, login_token, "admin_bill", ADMINISTRATOR), auth(seed_user, login_token, "recep_bill", RECEPTIONIST)


def seed_visit(db, uhid=UHID, lab_tests=("Complete Blood Count", "Lipid Profile")):
    """A finished OPD visit: patient, cardiology doctor, appointment, consultation, lab orders,
    one medicine dispensed (3 units) and a discharged 2-day general-ward admission."""
    if db.query(Patient).filter(Patient.uhid == uhid).one_or_none() is None:
        db.add(Patient(uhid=uhid, full_name="Billing Patient", age=50, gender="M", phone="9800000000", address=""))
    if db.query(Doctor).filter(Doctor.doctor_id == "DOC-000001").one_or_none() is None:
        db.add(Doctor(doctor_id="DOC-000001", full_name="Dr. Asha Rao", specialization="Cardiology", department="Cardiology"))
    db.flush()
    appointment = Appointment(patient_uhid=uhid, doctor_id="DOC-000001", slot_start=datetime(2026, 10, 27, 9, 0))
    db.add(appointment)
    db.flush()
    db.add(Consultation(appointment_id=appointment.id, patient_uhid=uhid, diagnosis="Hypertension"))
    for name in lab_tests:
        db.add(LabTestOrder(appointment_id=appointment.id, patient_uhid=uhid, test_name=name, ordered_by="doc1"))
    batch = MedicineBatch(medicine_name="Amlodipine 5mg", batch_number=f"B-{appointment.id}", quantity=100,
                          expiry_date=date(2030, 1, 1))
    db.add(batch)
    db.flush()
    db.add(PharmacyDispenseRecord(batch_id=batch.id, patient_uhid=uhid, quantity=3))
    bed = Bed(bed_number=f"G-{appointment.id}", ward="General")
    db.add(bed)
    db.flush()
    admitted = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
    admission = Admission(patient_uhid=uhid, bed_id=bed.id, admitted_at=admitted, discharged_at=admitted + timedelta(hours=30))
    db.add(admission)
    db.commit()
    return appointment, admission


def set_prices(client, admin):
    for category, item, price in [
        ("CONSULTATION", "Cardiology", "800.00"),
        ("CONSULTATION", "*", "500.00"),
        ("LAB", "Complete Blood Count", "250.00"),
        ("LAB", "*", "400.00"),
        ("PHARMACY", "Amlodipine 5mg", "12.50"),
        ("ROOM", "General", "1500.00"),
    ]:
        response = client.put(f"{BILLING_URL}/tariffs", headers=admin,
                              json={"category": category, "item_name": item, "unit_price": price})
        assert response.status_code == 200, response.text


def open_bill(client, recep, appointment=None, admission=None, uhid=UHID):
    response = client.post(f"{BILLING_URL}/bills", headers=recep, json={
        "patient_uhid": uhid,
        "appointment_id": appointment.id if appointment else None,
        "admission_id": admission.id if admission else None,
    })
    assert response.status_code == 201, response.text
    return response.json()


def consolidate(client, recep, bill_id):
    return client.post(f"{BILLING_URL}/bills/{bill_id}/consolidate", headers=recep)


def test_consolidated_bill_total_equals_sum_of_all_visit_charges(client, db_session, seed_user, login_token):
    # AC (US-17): the bill total equals the sum of all itemized charges for the visit.
    admin, recep = headers_for(seed_user, login_token)
    appointment, admission = seed_visit(db_session)
    set_prices(client, admin)
    bill = open_bill(client, recep, appointment, admission)

    response = consolidate(client, recep, bill["id"])

    assert response.status_code == 200, response.text
    data = response.json()
    lines = {(l["category"], l["description"]): (l["quantity"], l["unit_price"], l["amount"]) for l in data["line_items"]}
    assert lines == {
        ("CONSULTATION", "OPD consultation (Cardiology)"): (1, "800.00", "800.00"),
        ("LAB", "Lab test: Complete Blood Count"): (1, "250.00", "250.00"),
        ("LAB", "Lab test: Lipid Profile"): (1, "400.00", "400.00"),  # category default price
        ("PHARMACY", f"Medicine: Amlodipine 5mg (batch B-{appointment.id})"): (3, "12.50", "37.50"),
        ("ROOM", f"Bed G-{appointment.id}, General ward (2 days)"): (2, "1500.00", "3000.00"),
    }
    assert data["subtotal"] == "4487.50"
    assert data["total"] == "4487.50"
    assert db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "BILL_CONSOLIDATED").count() == 1


def test_consolidating_again_adds_only_new_charges(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session)
    set_prices(client, admin)
    bill = open_bill(client, recep, appointment)
    first = consolidate(client, recep, bill["id"]).json()

    again = consolidate(client, recep, bill["id"]).json()
    db_session.add(LabTestOrder(appointment_id=appointment.id, patient_uhid=UHID, test_name="ECG", ordered_by="doc1"))
    db_session.commit()
    later = consolidate(client, recep, bill["id"]).json()

    assert len(again["line_items"]) == len(first["line_items"])
    assert len(later["line_items"]) == len(first["line_items"]) + 1
    assert later["line_items"][-1]["description"] == "Lab test: ECG"


def test_a_charge_is_never_billed_on_two_bills(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session)
    set_prices(client, admin)
    first = open_bill(client, recep, appointment)
    second = open_bill(client, recep, appointment)

    consolidate(client, recep, first["id"])
    duplicate = consolidate(client, recep, second["id"]).json()

    assert duplicate["line_items"] == []
    assert duplicate["total"] == "0.00"


def test_missing_prices_are_listed_and_nothing_is_added(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session)
    client.put(f"{BILLING_URL}/tariffs", headers=admin, json={"category": "CONSULTATION", "item_name": "*", "unit_price": "500.00"})
    bill = open_bill(client, recep, appointment)

    response = consolidate(client, recep, bill["id"])

    assert response.status_code == 422
    missing = response.json()["detail"]["missing_prices"]
    assert "LAB: Complete Blood Count" in missing
    assert "PHARMACY: Amlodipine 5mg" in missing
    assert client.get(f"{BILLING_URL}/bills/{bill['id']}", headers=recep).json()["line_items"] == []


def test_admission_must_be_discharged_before_bed_charges_are_billed(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    appointment, admission = seed_visit(db_session)
    admission.discharged_at = None
    db_session.commit()
    set_prices(client, admin)
    bill = open_bill(client, recep, appointment, admission)

    assert consolidate(client, recep, bill["id"]).status_code == 409


def test_bill_cannot_be_opened_for_another_patients_visit(client, db_session, seed_user, login_token):
    _, recep = headers_for(seed_user, login_token)
    appointment, admission = seed_visit(db_session)
    db_session.add(Patient(uhid="HMS-000777", full_name="Someone Else", age=30, gender="F", phone="9811111111", address=""))
    db_session.commit()

    for field, value in (("appointment_id", appointment.id), ("admission_id", admission.id)):
        response = client.post(f"{BILLING_URL}/bills", headers=recep, json={"patient_uhid": "HMS-000777", field: value})
        assert response.status_code == 422


def test_only_admins_manage_the_tariff_and_schemes(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    price = {"category": "LAB", "item_name": "*", "unit_price": "100.00"}
    scheme = {"name": "Staff", "discount_percent": "10.00"}

    assert client.put(f"{BILLING_URL}/tariffs", headers=recep, json=price).status_code == 403
    assert client.post(f"{BILLING_URL}/discount-schemes", headers=recep, json=scheme).status_code == 403
    assert client.put(f"{BILLING_URL}/tariffs", headers=admin, json=price).status_code == 200
    assert client.post(f"{BILLING_URL}/discount-schemes", headers=admin, json=scheme).status_code == 201
    assert client.get(f"{BILLING_URL}/tariffs", headers=recep).json()[0]["unit_price"] == "100.00"
    # Setting the same item again updates the price instead of adding a duplicate.
    client.put(f"{BILLING_URL}/tariffs", headers=admin, json={**price, "unit_price": "120.00"})
    assert [t["unit_price"] for t in client.get(f"{BILLING_URL}/tariffs", headers=recep).json()] == ["120.00"]


def test_discounted_total_matches_the_configured_scheme(client, db_session, seed_user, login_token):
    # AC (US-17): the discounted total matches the configured scheme percentage/amount.
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session)
    set_prices(client, admin)
    percent_scheme = client.post(f"{BILLING_URL}/discount-schemes", headers=admin,
                                 json={"name": "Senior citizen", "discount_percent": "20.00"}).json()
    flat_scheme = client.post(f"{BILLING_URL}/discount-schemes", headers=admin,
                              json={"name": "Insurance co-pay", "discount_amount": "300.00"}).json()
    bill = open_bill(client, recep, appointment)
    consolidate(client, recep, bill["id"])  # 800 + 250 + 400 + 37.50 = 1487.50

    percent = client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep, json={"scheme_id": percent_scheme["id"]}).json()
    assert percent["total"] == "1190.00"  # 1487.50 - 20% (297.50)
    assert percent["discount_reason"] == "Scheme: Senior citizen"
    assert percent["discount_scheme_id"] == percent_scheme["id"]

    flat = client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep, json={"scheme_id": flat_scheme["id"]}).json()
    assert flat["total"] == "1187.50"


def test_inactive_scheme_and_unexplained_manual_discount_are_rejected(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session)
    set_prices(client, admin)
    scheme = client.post(f"{BILLING_URL}/discount-schemes", headers=admin, json={"name": "Old", "discount_percent": "5.00"}).json()
    client.post(f"{BILLING_URL}/discount-schemes/{scheme['id']}/deactivate", headers=admin)
    bill = open_bill(client, recep, appointment)
    consolidate(client, recep, bill["id"])

    assert client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep, json={"scheme_id": scheme["id"]}).status_code == 409
    assert client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep, json={"discount_percent": "5.00"}).status_code == 422
    assert client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep,
                       json={"discount_percent": "5.00", "reason": "Goodwill"}).status_code == 200


def test_payment_status_overpayment_and_discount_after_payment(client, db_session, seed_user, login_token):
    # HMS-F-019: a valid payment updates the bill status; invalid payments are rejected.
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session)
    set_prices(client, admin)
    bill = open_bill(client, recep, appointment)
    consolidate(client, recep, bill["id"])  # total 1487.50
    pay = f"{BILLING_URL}/bills/{bill['id']}/payments"

    assert client.post(pay, headers=recep, json={"amount": "2000.00", "method": "CASH"}).status_code == 422
    partial = client.post(pay, headers=recep, json={"amount": "487.50", "method": "UPI"}).json()
    assert partial["status"] == "PARTIALLY_PAID"
    assert partial["payments"][0]["receipt_number"].startswith("RCPT-")

    late_discount = client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep,
                                json={"discount_percent": "10.00", "reason": "Late"})
    assert late_discount.status_code == 409

    paid = client.post(pay, headers=recep, json={"amount": "1000.00", "method": "CARD"}).json()
    assert paid["status"] == "PAID"
    assert paid["balance_due"] == "0.00"
    assert consolidate(client, recep, bill["id"]).status_code == 409  # finalized


def test_bill_discounted_to_zero_is_marked_paid(client, db_session, seed_user, login_token):
    admin, recep = headers_for(seed_user, login_token)
    appointment, _ = seed_visit(db_session, lab_tests=())
    set_prices(client, admin)
    free = client.post(f"{BILLING_URL}/discount-schemes", headers=admin, json={"name": "Charity", "discount_percent": "100.00"}).json()
    bill = open_bill(client, recep, appointment)
    consolidate(client, recep, bill["id"])

    result = client.post(f"{BILLING_URL}/bills/{bill['id']}/discount", headers=recep, json={"scheme_id": free["id"]}).json()

    assert result["total"] == "0.00"
    assert result["status"] == "PAID"
