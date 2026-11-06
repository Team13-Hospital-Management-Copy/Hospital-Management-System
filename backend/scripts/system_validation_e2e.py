"""System Validation (US-21 / NFR verification companion): a real end-to-end run.

Not a pytest file - this is deliberately a standalone script that drives the full,
multi-module hospital workflow against a LIVE running server over real HTTP, the same way a
human tester would, rather than through FastAPI's in-process TestClient. It's the evidence
behind docs/reports/system_validation_report.md.

Chain exercised (a superset of the Test Plan's example workflow,
Section 5.1.3: "Patient Registration -> Appointment Scheduling -> Doctor Consultation ->
Medical Record Update -> Prescription -> Billing -> Payment"):

    Doctor setup -> Patient registration -> Appointment booking -> Consultation ->
    Lab test order + result -> Prescription -> Pharmacy dispense -> Bill consolidation ->
    Discount -> Payment -> Operational report

Usage:
    # Terminal 1
    cd backend && rm -f /tmp/sysval.db && DATABASE_URL=sqlite:////tmp/sysval.db \
        uvicorn app.main:app --port 8099

    # Terminal 2
    cd backend && python scripts/system_validation_e2e.py --base-url http://127.0.0.1:8099
"""

import argparse
import sys
from datetime import date, timedelta

import httpx


class Step:
    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        print(f"  {self.name} ... ", end="", flush=True)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            print("PASS")
        else:
            print(f"FAIL ({exc})")
        return False  # never swallow - a failure must stop the run


def seed_users(db_url: str) -> None:
    import os

    os.environ["DATABASE_URL"] = db_url
    from app.database import Base, SessionLocal, engine
    from app.models import User
    from app.roles import ADMINISTRATOR, DOCTOR, PHARMACIST, RECEPTIONIST
    from app.security import hash_password

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for username, role in [
        ("sysval_admin", ADMINISTRATOR),
        ("sysval_reception", RECEPTIONIST),
        ("sysval_doctor", DOCTOR),
        ("sysval_pharmacist", PHARMACIST),
    ]:
        if not db.query(User).filter_by(username=username).one_or_none():
            db.add(User(username=username, password_hash=hash_password("Valid#Pass123"), role=role))
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8099")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=10.0)

    def login(username: str) -> dict:
        r = client.post("/auth/login", json={"username": username, "password": "Valid#Pass123"})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['token']}"}

    admin = login("sysval_admin")
    reception = login("sysval_reception")
    doctor = login("sysval_doctor")
    pharmacist = login("sysval_pharmacist")

    tomorrow = date.today() + timedelta(days=1)

    with Step("Doctor setup (US-07)"):
        r = client.post(
            "/doctors",
            headers=admin,
            json={
                "full_name": "Sys Validation",
                "specialization": "General Medicine",
                "department": "General Medicine",
                "slot_minutes": 30,
                "schedule": [{"weekday": tomorrow.weekday(), "start_time": "09:00", "end_time": "11:00"}],
            },
        )
        r.raise_for_status()
        doctor_id = r.json()["doctor_id"]

    with Step("Patient registration (US-05)"):
        r = client.post(
            "/patients/",
            headers=reception,
            json={"full_name": "System Validation Patient", "age": 44, "gender": "F", "phone": "9000000001"},
        )
        r.raise_for_status()
        uhid = r.json()["uhid"]

    with Step("Appointment booking (US-08/09)"):
        r = client.post(
            "/appointments/opd",
            headers=reception,
            json={"patient_uhid": uhid, "doctor_id": doctor_id, "slot_start": f"{tomorrow}T09:00:00"},
        )
        r.raise_for_status()
        appointment_id = r.json()["id"]

    with Step("Doctor consultation (US-12)"):
        r = client.post(
            "/consultations",
            headers=doctor,
            json={"appointment_id": appointment_id, "diagnosis": "Seasonal flu", "blood_pressure": "118/76"},
        )
        r.raise_for_status()
        consultation_id = r.json()["id"]

    with Step("Lab test order + result (US-14)"):
        r = client.post("/lab-tests", headers=doctor, json={"appointment_id": appointment_id, "test_name": "CBC"})
        r.raise_for_status()
        lab_id = r.json()["id"]
        r = client.post(f"/lab-tests/{lab_id}/result", headers=doctor, json={"result": "Within normal range"})
        r.raise_for_status()

    with Step("Prescription (US-13)"):
        r = client.post(
            "/prescriptions",
            headers=doctor,
            json={
                "consultation_id": consultation_id,
                "drug_name": "Paracetamol",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "duration": "5 days",
            },
        )
        r.raise_for_status()

    with Step("Pharmacy dispense (US-18)"):
        r = client.post(
            "/pharmacy/batches",
            headers=pharmacist,
            json={
                "medicine_name": "Paracetamol",
                "batch_number": "SYSVAL-1",
                "quantity": 100,
                "expiry_date": str(date.today() + timedelta(days=365)),
            },
        )
        r.raise_for_status()
        batch_id = r.json()["id"]
        r = client.post(
            "/pharmacy/dispense", headers=pharmacist, json={"batch_id": batch_id, "patient_uhid": uhid, "quantity": 10}
        )
        r.raise_for_status()

    with Step("Set tariff prices (US-17 config)"):
        for category, item_name, price in [
            ("CONSULTATION", "*", "500.00"),
            ("LAB", "CBC", "300.00"),
            ("PHARMACY", "Paracetamol", "5.00"),
        ]:
            r = client.put(
                "/billing/tariffs", headers=admin,
                json={"category": category, "item_name": item_name, "unit_price": price},
            )
            r.raise_for_status()

    with Step("Bill consolidation (US-17)"):
        r = client.post("/billing/bills", headers=reception, json={"patient_uhid": uhid, "appointment_id": appointment_id})
        r.raise_for_status()
        bill_id = r.json()["id"]
        r = client.post(f"/billing/bills/{bill_id}/consolidate", headers=reception)
        r.raise_for_status()
        bill = r.json()
        print(f"    subtotal={bill['subtotal']}", end="  ")

    with Step("Discount (US-17)"):
        r = client.post(
            "/billing/bills/{}/discount".format(bill_id),
            headers=reception,
            json={"discount_percent": "10.00", "reason": "System validation test discount"},
        )
        r.raise_for_status()
        bill = r.json()
        print(f"total={bill['total']}", end="  ")

    with Step("Payment + receipt (US-17)"):
        r = client.post(
            f"/billing/bills/{bill_id}/payments", headers=reception, json={"amount": bill["total"], "method": "CASH"}
        )
        r.raise_for_status()
        bill = r.json()
        assert bill["status"] == "PAID", f"expected PAID, got {bill['status']}"
        assert bill["payments"][0]["receipt_number"].startswith("RCPT-")

    with Step("Operational report reflects the bill (US-20)"):
        r = client.get(
            "/admin/reports/summary",
            headers=admin,
            params={"start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=2))},
        )
        r.raise_for_status()
        report = r.json()
        assert float(report["revenue"]) >= float(bill["amount_paid"]), "revenue report doesn't include the payment"

    with Step("EHR view shows the full visit history (US-15)"):
        r = client.get(f"/patients/{uhid}/ehr", headers=doctor)
        r.raise_for_status()
        ehr = r.json()
        assert len(ehr["visits"]) == 1
        assert len(ehr["visits"][0]["prescriptions"]) == 1
        assert len(ehr["visits"][0]["lab_tests"]) == 1

    print("\nAll system validation steps passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
