"""US-20 / HMS-F-020 / TC-Admin-02: operational reports, exportable to PDF/CSV."""

from datetime import date, datetime, timedelta

from app.models import Admission, Appointment, Bed, Bill, Patient, Payment
from app.roles import ADMINISTRATOR, RECEPTIONIST

REPORTS_URL = "/admin/reports"


def admin_auth(seed_user, login_token, username="admin_us20"):
    seed_user(username=username, role=ADMINISTRATOR)
    return {"Authorization": f"Bearer {login_token(username)}"}


def seed_patient(db_session, uhid="HMS-000501"):
    patient = Patient(
        uhid=uhid, full_name="Reports Test Patient", age=38, gender="M", phone="9876511111", address=""
    )
    db_session.add(patient)
    db_session.commit()
    return patient


def test_reports_require_admin_role(client, db_session, seed_user, login_token):
    seed_user(username="receptionist_us20", role=RECEPTIONIST)
    headers = {"Authorization": f"Bearer {login_token('receptionist_us20')}"}

    response = client.get(
        f"{REPORTS_URL}/summary", headers=headers, params={"start_date": "2026-10-01", "end_date": "2026-10-31"}
    )

    assert response.status_code == 403


def test_end_date_before_start_date_rejected(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)

    response = client.get(
        f"{REPORTS_URL}/summary", headers=headers, params={"start_date": "2026-10-31", "end_date": "2026-10-01"}
    )

    assert response.status_code == 422


def test_opd_footfall_counts_only_booked_appointments_in_range(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)
    patient = seed_patient(db_session)

    db_session.add_all(
        [
            Appointment(patient_uhid=patient.uhid, doctor_id="DOC-1", slot_start=datetime(2026, 10, 10, 9, 0), status="BOOKED"),
            Appointment(patient_uhid=patient.uhid, doctor_id="DOC-1", slot_start=datetime(2026, 10, 15, 9, 0), status="BOOKED"),
            # Outside the range - should not be counted.
            Appointment(patient_uhid=patient.uhid, doctor_id="DOC-1", slot_start=datetime(2026, 11, 5, 9, 0), status="BOOKED"),
            # Cancelled within range - should not be counted as footfall.
            Appointment(patient_uhid=patient.uhid, doctor_id="DOC-1", slot_start=datetime(2026, 10, 20, 9, 0), status="CANCELLED"),
        ]
    )
    db_session.commit()

    response = client.get(
        f"{REPORTS_URL}/summary", headers=headers, params={"start_date": "2026-10-01", "end_date": "2026-10-31"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["opd_footfall"] == 2


def test_revenue_matches_payment_records_in_range(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)
    patient = seed_patient(db_session)

    bill = Bill(patient_uhid=patient.uhid)
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(bill)

    db_session.add_all(
        [
            Payment(bill_id=bill.id, amount="500.00", method="CASH", receipt_number="RCPT-A", paid_at=datetime(2026, 10, 10, 10, 0)),
            Payment(bill_id=bill.id, amount="250.50", method="CARD", receipt_number="RCPT-B", paid_at=datetime(2026, 10, 20, 10, 0)),
            # Outside the range.
            Payment(bill_id=bill.id, amount="999.00", method="UPI", receipt_number="RCPT-C", paid_at=datetime(2026, 11, 5, 10, 0)),
        ]
    )
    db_session.commit()

    response = client.get(
        f"{REPORTS_URL}/summary", headers=headers, params={"start_date": "2026-10-01", "end_date": "2026-10-31"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["revenue"] == "750.50"


def test_bed_occupancy_computed_from_admission_overlap(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)
    patient = seed_patient(db_session)

    bed = Bed(bed_number="B-1", ward="General")
    db_session.add(bed)
    db_session.commit()
    db_session.refresh(bed)

    # Admitted Oct 5, discharged Oct 10: 6 days overlap with an Oct 1-31 range.
    db_session.add(
        Admission(
            patient_uhid=patient.uhid,
            bed_id=bed.id,
            admitted_at=datetime(2026, 10, 5),
            discharged_at=datetime(2026, 10, 10),
        )
    )
    db_session.commit()

    response = client.get(
        f"{REPORTS_URL}/summary", headers=headers, params={"start_date": "2026-10-01", "end_date": "2026-10-31"}
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["admissions_in_range"] == 1
    assert data["occupied_bed_days"] == 6
    assert data["available_bed_days"] == 31
    assert abs(data["bed_occupancy_rate"] - 6 / 31) < 0.001


def test_export_csv_matches_summary(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)
    seed_patient(db_session)

    response = client.get(
        f"{REPORTS_URL}/export",
        headers=headers,
        params={"start_date": "2026-10-01", "end_date": "2026-10-31", "format": "csv"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "Hospital Management System" in body
    assert "OPD Footfall" in body


def test_export_pdf_returns_pdf_bytes(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)
    seed_patient(db_session)

    response = client.get(
        f"{REPORTS_URL}/export",
        headers=headers,
        params={"start_date": "2026-10-01", "end_date": "2026-10-31", "format": "pdf"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_invalid_export_format_rejected(client, db_session, seed_user, login_token):
    headers = admin_auth(seed_user, login_token)

    response = client.get(
        f"{REPORTS_URL}/export",
        headers=headers,
        params={"start_date": "2026-10-01", "end_date": "2026-10-31", "format": "xml"},
    )

    assert response.status_code == 422
