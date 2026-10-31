"""US-21 NFR verification.

Covers what's genuinely automatable from the story's acceptance criteria:
- AC-HMS-SR-004 (audit logs for record changes AND reads, per the issue's own wording):
  every create/read on an EHR record (consultation, prescription, lab test) is logged.
- AC-HMS-NF-001 (performance): a concurrency/response-time smoke test, scaled down from
  "200 concurrent users" to what's meaningful against a single local dev server - see
  NFR_VERIFICATION.md for why the full-scale load test and the two human-subject ACs
  (usability study, production uptime monitoring) are out of reach here and how that's
  handled honestly instead of being faked.
"""

import statistics
import time
from datetime import datetime, timedelta

from app.models import Appointment, AuditLogEntry, Patient
from app.roles import DOCTOR

RESPONSE_TIME_BUDGET_SECONDS = 3.0
SAMPLE_SIZE = 200


def test_ehr_create_and_read_operations_are_audit_logged(client, db_session, seed_user, login_token):
    seed_user(username="doctor_nfr", role=DOCTOR)
    headers = {"Authorization": f"Bearer {login_token('doctor_nfr')}"}

    patient = Patient(
        uhid="HMS-000601", full_name="NFR Test Patient", age=50, gender="F", phone="9876522222", address=""
    )
    db_session.add(patient)
    db_session.commit()

    appointment = Appointment(
        patient_uhid=patient.uhid,
        doctor_id="DOC-NFR",
        slot_start=datetime.now() + timedelta(days=1),
        status="BOOKED",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    # Create: consultation.
    consultation = client.post(
        "/consultations",
        headers=headers,
        json={"appointment_id": appointment.id, "diagnosis": "NFR verification case"},
    ).json()
    assert (
        db_session.query(AuditLogEntry).filter_by(event_type="CONSULTATION_CREATED").count() == 1
    )

    # Create: prescription against that consultation.
    client.post(
        "/prescriptions",
        headers=headers,
        json={
            "consultation_id": consultation["id"],
            "drug_name": "Ibuprofen",
            "dosage": "200 mg",
            "frequency": "Once daily",
            "duration": "3 days",
        },
    )
    assert (
        db_session.query(AuditLogEntry).filter_by(event_type="PRESCRIPTION_CREATED").count() == 1
    )

    # Create: lab test order + result.
    order = client.post(
        "/lab-tests", headers=headers, json={"appointment_id": appointment.id, "test_name": "CBC"}
    ).json()
    client.post(f"/lab-tests/{order['id']}/result", headers=headers, json={"result": "Normal"})
    assert db_session.query(AuditLogEntry).filter_by(event_type="LAB_TEST_ORDERED").count() == 1
    assert (
        db_session.query(AuditLogEntry).filter_by(event_type="LAB_TEST_RESULT_RECORDED").count() == 1
    )

    # Read: the longitudinal EHR view aggregating all of the above.
    ehr_response = client.get(f"/patients/{patient.uhid}/ehr", headers=headers)
    assert ehr_response.status_code == 200, ehr_response.text
    assert db_session.query(AuditLogEntry).filter_by(event_type="EHR_VIEWED").count() == 1


def test_representative_endpoint_response_time_under_budget(client, seed_user, login_token):
    """AC-HMS-NF-001, honestly scaled down: P90 latency stays within the 3-second budget.

    The AC asks for 200 *concurrent* users. Genuine multi-threaded concurrency isn't safe to
    test here: the test harness's SQLite connection (StaticPool, a single shared connection so
    `db_session` and the app see the same data) isn't safe for simultaneous multi-threaded
    access - trying it throws `sqlite3.InterfaceError: bad parameter or other API misuse` from
    the driver itself, not from application code. A full concurrent load test needs dedicated
    load-testing infrastructure (e.g. Locust/k6 against a real multi-connection Postgres
    deployment) that this project doesn't have.

    What this measures instead, honestly: P90 latency over SAMPLE_SIZE sequential requests to a
    representative read endpoint - real evidence that individual transactions are fast, just not
    evidence about concurrent throughput. See NFR_VERIFICATION.md for the full caveat.
    """
    seed_user(username="doctor_perf", role=DOCTOR)
    headers = {"Authorization": f"Bearer {login_token('doctor_perf')}"}

    durations = []
    for _ in range(SAMPLE_SIZE):
        start = time.perf_counter()
        response = client.get("/doctors", headers=headers)
        durations.append(time.perf_counter() - start)
        assert response.status_code == 200

    p90 = statistics.quantiles(durations, n=10)[8]
    assert p90 <= RESPONSE_TIME_BUDGET_SECONDS, (
        f"P90 response time {p90:.3f}s exceeded the {RESPONSE_TIME_BUDGET_SECONDS}s budget "
        f"across {SAMPLE_SIZE} sequential requests"
    )
