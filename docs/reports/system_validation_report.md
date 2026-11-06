# System Validation Report

- **Date executed:** 2026-11-05
- **Build:** `main` (PR #45 merged) + pending PR #46 (requirement-ID alignment, comment-only)
- **Environment:** a live `uvicorn` server (not the in-process test client), real HTTP requests,
  a fresh SQLite database
- **Script:** [`backend/scripts/system_validation_e2e.py`](../../backend/scripts/system_validation_e2e.py)
- **How to reproduce:**
  ```bash
  cd backend
  rm -f /tmp/sysval.db
  DATABASE_URL=sqlite:////tmp/sysval.db uvicorn app.main:app --port 8099 &
  python -c "from scripts.system_validation_e2e import seed_users; seed_users('sqlite:////tmp/sysval.db')"
  python scripts/system_validation_e2e.py --base-url http://127.0.0.1:8099
  ```

## Purpose

Per Test Plan §5.1.3 (System Testing): "The complete Hospital Management System will be
tested as an integrated system... End-to-end workflows will be tested, such as: Patient
Registration → Appointment Scheduling → Doctor Consultation → Medical Record Update →
Prescription → Billing → Payment." This report is exactly that workflow, run for real - a
superset covering 13 of the 21 backlog stories in one continuous chain, each step's output
feeding the next, exactly as a receptionist/doctor/pharmacist/administrator would actually use
the system in sequence.

This is intentionally different from the [Unit Test Report](unit_test_report.md): that suite
tests each module largely on its own; this script never touches the test database directly and
never runs in-process - every step is a real HTTP call to a real running server, and a later
step only succeeds if an earlier step's real response (a UHID, an appointment ID, a bill ID)
was correct.

## Results

| # | Step | Story | Result |
|---|---|---|---|
| 1 | Set up a doctor profile and schedule | US-07 | **PASS** |
| 2 | Register a patient | US-05 | **PASS** |
| 3 | Book an OPD appointment | US-08 / US-09 | **PASS** |
| 4 | Record a doctor consultation | US-12 | **PASS** |
| 5 | Order and record a lab test result | US-14 | **PASS** |
| 6 | Create an electronic prescription | US-13 | **PASS** |
| 7 | Dispense medicine from pharmacy stock | US-18 | **PASS** |
| 8 | Configure service tariff prices | US-17 (admin config) | **PASS** |
| 9 | Consolidate the visit's bill (consultation + lab + pharmacy, auto-priced from the tariff) | US-17 | **PASS** — subtotal **₹850.00** (500 consultation + 300 lab + 50 pharmacy), matching the sum of every itemized charge exactly |
| 10 | Apply a 10% discount | US-17 | **PASS** — total **₹765.00** (850.00 − 10%), matching the configured discount exactly |
| 11 | Record full payment and receive a receipt | US-17 | **PASS** — bill status transitioned to `PAID`, receipt number issued in the `RCPT-########` format |
| 12 | Operational report reflects the new revenue | US-20 | **PASS** — the report's revenue figure for the period includes this payment |
| 13 | Longitudinal EHR view shows the full visit | US-15 | **PASS** — one visit returned, with exactly the one prescription and one lab test created above attached to it |

**13 / 13 steps passed.** Zero manual intervention or data correction was needed between
steps - every ID returned by one step (doctor ID, UHID, appointment ID, consultation ID, bill
ID) was consumed directly by the next, which is itself evidence that the modules' real
interfaces (not just their individually-tested behavior) are compatible.

## What this does and doesn't demonstrate

- **Does:** real cross-module data flow, real pricing/discount arithmetic, real audit-logged
  state transitions (`OPEN` → `PARTIALLY_PAID`/`PAID`), real aggregation across four different
  clinical modules into one EHR view and one revenue report.
- **Doesn't:** concurrent/multi-user load (see `backend/NFR_VERIFICATION.md` for why that's out
  of reach here), IPD bed-admission billing (not exercised in this particular run, though
  covered separately by `test_inpatient.py` and `test_billing_consolidation.py`), or anything
  involving a real external payment/SMS/email/lab gateway (all mocked by design throughout the
  project, documented at each point they're used).
