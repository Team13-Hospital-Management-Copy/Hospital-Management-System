# Unit Test Report

- **Date generated:** 2026-11-05
- **Build:** `main` (PR #45 merged) + pending PR #46 (requirement-ID alignment, comment-only)
- **Environment:** Python 3.12.3, pytest 8.3.4, FastAPI 0.115.6, SQLite (in-memory, `StaticPool`)
- **How to reproduce:** `cd backend && pytest -v`
- **Raw results:** [`junit_results.xml`](junit_results.xml) (JUnit XML, importable into any CI/test
  dashboard)

## What "unit" means here

Every test in this suite runs through FastAPI's `TestClient` against a real (in-memory)
SQLite database, not against mocked business logic - so by a strict definition these are
module-level/component tests, closer to the Test Plan's own §5.1.1 Unit Testing examples
("Testing user authentication. Testing patient registration. Testing appointment validation.
Testing bill calculation.") than to isolated-function unit tests with every dependency
mocked out. That's a deliberate choice, not an oversight: for an API-centric system like this
one, a test that never touches a real request/response cycle or a real database constraint
(e.g. the double-booking unique index) would miss exactly the bugs that matter most. The
separate [System Validation Report](system_validation_report.md) covers genuine end-to-end,
multi-module, live-server validation; this report is the per-module/per-story layer beneath
it.

## Summary

| Metric | Value |
|---|---|
| Total tests | 197 |
| Passed | 197 |
| Failed | 0 |
| Errors | 0 |

## Results by test file (one file per user story)

| Test file | Story | Tests | Result |
|---|---|---:|---|
| `test_login.py` | US-01 Secure Staff Login & Lockout | 6 | PASS |
| `test_tls.py` | US-02 TLS 1.2+ Enforcement | 16 | PASS |
| `test_session_timeout.py` | US-03 Session Timeout & Logout | 7 | PASS |
| `test_rbac.py` | US-04 RBAC Enforcement | 6 | PASS |
| `test_patients.py` | US-05 Patient Registration & UHID | 8 | PASS |
| `test_patient_search.py` | US-06 Patient Search & Retrieval | 21 | PASS |
| `test_doctors.py` | US-07 Doctor Profile & Availability | 9 | PASS |
| `test_opd_booking.py` | US-08 Book OPD Appointment | 7 | PASS |
| `test_appointment_double_booking.py` | US-09 Prevent Double-Booking | 11 | PASS |
| `test_appointment_reschedule_cancel.py` | US-10 Reschedule/Cancel Appointment | 10 | PASS |
| `test_appointment_notifications.py` | US-11 Confirmation & Reminders | 8 | PASS |
| `test_consultations.py` | US-12 Diagnosis, Vitals & Notes | 4 | PASS |
| `test_prescriptions.py` | US-13 Electronic Prescriptions | 5 | PASS |
| `test_lab_tests.py` | US-14 Order & Record Lab Tests | 11 | PASS |
| `test_ehr.py` | US-15 Longitudinal Patient EHR | 6 | PASS |
| `test_inpatient.py` | US-16 Bed/Ward Admission & Discharge | 8 | PASS |
| `test_billing.py` + `test_billing_consolidation.py` | US-17 Consolidated Billing & Payments | 24 | PASS |
| `test_pharmacy.py` | US-18 Pharmacy Dispensing & Stock | 7 | PASS |
| `test_staff_accounts.py` | US-19 Staff Account & Role Admin | 13 | PASS |
| `test_reports.py` | US-20 Operational Reports PDF/CSV | 8 | PASS |
| `test_nfr_verification.py` | US-21 NFR Verification | 2 | PASS |
| **Total** | **All 21 stories** | **197** | **PASS** |

Every one of the 21 backlog stories has a dedicated test file and every file passes - full
story-level test coverage, not just line coverage (see the
[Code Coverage Report](code_coverage_report.md) for that separate metric).
