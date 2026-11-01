# Test Results — Sprint 2 (US-14, US-17) and SRS v2 alignment

- **Story owner:** parnikahallalli
- **Date executed:** 1 Nov 2026
- **Build:** branch `fix/srs-v2-alignment`
- **Environment:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, SQLite
- **How to re-run:** `cd backend && pytest -v tests/test_lab_tests.py tests/test_billing.py tests/test_billing_consolidation.py tests/test_appointment_reschedule_cancel.py`
- **Overall:** 35 / 35 lab and billing tests passed. Full backend suite: see the PR (all passing).

Requirement and test-case IDs below follow the **SRS v2** (`Team-13_SRS.pdf`). The GitHub issues use the
first SRS's numbers; the mapping for these stories is:

| Story | First SRS (issue) | SRS v2 | Test case (SRS v2) |
| --- | --- | --- | --- |
| US-08 Book OPD appointment | HMS-F-005 | HMS-F-009 | TC-Apt-01 |
| US-09 Prevent double-booking | HMS-F-006 | HMS-F-010 | TC-Apt-02 |
| US-10 Reschedule/cancel | HMS-F-007 | HMS-F-011 | TC-Apt-03 |
| US-11 Notifications | HMS-F-008 | HMS-F-012 | TC-Apt-04 |
| US-14 Lab tests | HMS-F-011 | HMS-F-014 (clinical information) | TC-Med-02 |
| US-17 Billing | HMS-F-014/015/016 | HMS-F-018 (bills), HMS-F-019 (payments) | TC-Bill-01, TC-Bill-02 |
| US-02 TLS | HMS-SR-001 | HMS-SR-002, HMS-NF-003 | TC-Sec-05, TC-Sec-01 |

## TC-Med-02 — Order & record lab tests (US-14, HMS-F-014)

**Acceptance criterion (US-14):** a test order moves Ordered → Completed with results attached.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| Med-02.1 | Doctor orders a test for a booked appointment | `201`, status `ORDERED`, linked to the appointment's patient | PASS |
| Med-02.2 | Doctor records the result | Status `COMPLETED`, result and completion time stored | PASS |
| Med-02.3 | Record a second result | `409` | PASS |
| Med-02.4 | Order for a missing / cancelled appointment | `404` / `400` | PASS |
| Med-02.5 | Blank test name / blank result / missing order | `422` / `422` / `404` | PASS |
| Med-02.6 | Non-doctor orders or lists tests | `403` | PASS |
| Med-02.7 | List a patient's tests | Both ordered and completed tests returned | PASS |
| Med-02.8 | Ordered test appears on the visit's bill (see Bill-01.1) | Priced line `Lab test: <name>` | PASS |

Results are entered manually; no Laboratory Information System is connected (playbook §9 risk).

## TC-Bill-01 — Bill generation (US-17, HMS-F-018)

**Acceptance criteria:** a bill is generated with the correct patient details, services, charges and total (HMS-F-018); the bill total equals the sum of all itemized charges for the visit; the discounted total matches the configured scheme (US-17).

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| Bill-01.1 | Consolidate a visit with consultation, 2 lab tests, 3 units of a medicine and a 30-hour stay | 5 lines: 800 + 250 + 400 (category default) + 3×12.50 + 2 days×1500 = **4487.50**; total equals the sum | PASS |
| Bill-01.2 | Consolidate again, then again after a new lab test | First repeat adds nothing; later run adds only the new test | PASS |
| Bill-01.3 | Second bill for the same visit | Nothing added: no record is billed twice | PASS |
| Bill-01.4 | Items with no price | `422` listing each missing price; nothing added | PASS |
| Bill-01.5 | Admission not yet discharged | `409` | PASS |
| Bill-01.6 | Appointment or admission of a different patient | `422` | PASS |
| Bill-01.7 | Manual line items (original tests) | Total = sum of items; bad category `422` | PASS |
| Bill-01.8 | Configured 20 % scheme on 1487.50 / flat 300 scheme | Total 1190.00 / 1187.50, reason "Scheme: …" | PASS |
| Bill-01.9 | Inactive scheme / manual discount without reason / with reason | `409` / `422` / `200` | PASS |
| Bill-01.10 | Flat discount above subtotal; both percent and amount | `422` | PASS |
| Bill-01.11 | Bill discounted to zero | Total 0.00, status `PAID` | PASS |
| Bill-01.12 | Receptionist tries to set prices or create schemes; admin does | `403`; admin `200`/`201`; re-setting a price updates it | PASS |

## TC-Bill-02 — Payment recording (US-17, HMS-F-019)

**Acceptance criteria:** a valid payment updates the bill status correctly (HMS-F-019); a receipt is generated immediately after payment (US-17).

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| Bill-02.1 | Pay part of the bill | Status `PARTIALLY_PAID`, receipt `RCPT-…`, correct balance | PASS |
| Bill-02.2 | Pay the rest | Status `PAID`, balance 0.00 | PASS |
| Bill-02.3 | Pay more than the balance | `422` | PASS |
| Bill-02.4 | Change the discount after a payment | `409` | PASS |
| Bill-02.5 | Change a `PAID` bill (items, consolidate) | `409` | PASS |
| Bill-02.6 | Invalid payment method | `422` | PASS |

## TC-Apt-03 — Authorized cancel/reschedule (US-10, HMS-F-011)

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| Apt-03.8 | Doctor cancels and reschedules; pharmacist tries to cancel | Doctor `200`; pharmacist `403` | PASS |
| Apt-03.9 | Audit log after cancel/reschedule | `APPOINTMENT_CANCELLED` / `APPOINTMENT_RESCHEDULED` with the user | PASS |

## Not covered

- No real payment gateway (card/UPI recorded like cash) and no LIS; both are mocks.
- A `PATIENT` account is not linked to a patient record, so the system can't yet restrict a patient to their own appointments.

## Open defects

None.
