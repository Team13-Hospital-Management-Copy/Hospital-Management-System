# TC-APT Test Results — Sprint 1 (US-09, US-10, US-11)

- **Owner:** parnikahallalli
- **Date executed:** 19 Oct 2026
- **Build:** branch `feature/us-09-10-11-appointment-lifecycle`
- **Environment:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, SQLite (in-memory for unit/API tests, file-based for the concurrency test)
- **How to re-run:** `cd backend && pytest -v tests/test_appointment_*.py`
- **Overall:** 23 / 23 passed, 0 failed. Full backend suite (incl. US-01): 29 / 29 passed.

Requirement numbering follows the SRS (§4.2), not the Test Plan's §3.1 table (see playbook §9).

## TC-Appt-02 — Prevent double-booking (US-09, HMS-F-006)

**Acceptance criterion (AC-HMS-F-006):** concurrent booking attempts for the same slot result in exactly one success.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| 02.1 | 10 threads book the same doctor + slot at the same instant | Exactly 1 booked, 9 rejected, 1 row in DB | PASS |
| 02.2 | Second booking for same doctor + slot (sequential) | `409 Conflict`, 1 row in DB | PASS |
| 02.3 | Same slot with a different doctor / different slot with same doctor | Both allowed (`201`) | PASS |
| 02.4 | Same instant sent as `10:00Z` and `15:30+05:30` | Treated as the same slot → second is `409` | PASS |
| 02.5 | Slot in the past | `400` | PASS |
| 02.6 | `GET /appointments/booked-slots` after a booking | Shows the taken slot | PASS |
| 02.7–9 | Missing `patient_uhid` / `doctor_id` / `slot_start` | `422` | PASS |

## TC-Appt-03 — Reschedule or cancel (US-10, HMS-F-007)

**Acceptance criterion (AC-HMS-F-007):** cancelling releases the slot; rescheduling moves the booking without creating a duplicate.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| 03.1 | Cancel, then another patient books the same slot | Cancel `200`, re-book `201` | PASS |
| 03.2 | Reschedule 10:00 → 11:00 | Same appointment ID, slot moved, still 1 row; 10:00 bookable again | PASS |
| 03.3 | Reschedule into a slot someone else holds | `409`, original slot unchanged | PASS |
| 03.4 | Cancel/reschedule 1h before slot with 2h cutoff | `400` with cutoff message | PASS |
| 03.5 | Same as 03.4 but cutoff configured to 0.5h | Cancel allowed (`200`) | PASS |
| 03.6 | Cancel an already-cancelled / non-existent appointment | `409` / `404` | PASS |
| 03.7 | Reschedule into the past / reschedule a cancelled appointment | `400` / `409` | PASS |

## TC-Appt-04 — Confirmation & reminder notifications (US-11, HMS-F-008)

**Acceptance criterion (AC-HMS-F-008):** a confirmation is sent within 1 minute of booking and a reminder 24 hours prior.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| 04.1 | Book an appointment | Confirmation sent on SMS + e-mail, `sent_at` < 1 min after booking | PASS |
| 04.2 | Reminder timing | Reminder queued for exactly slot − 24h; not sent 1 min early; sent at the due time; not re-sent | PASS |
| 04.3 | Booking < 24h ahead | Confirmation only, no reminder | PASS |
| 04.4 | Cancel | Pending reminders cancelled, cancellation notice sent, nothing sent later | PASS |
| 04.5 | Reschedule | Old reminders cancelled, new reminder at new slot − 24h, new confirmation sent | PASS |
| 04.6 | Gateway down at booking time | Booking still succeeds; send marked FAILED; dispatcher retries and sends it | PASS |
| 04.7 | `GET /appointments/{id}/notifications` | Lists confirmation + reminder history | PASS |

**Note:** SMS/e-mail delivery uses a mock gateway (no real gateway available yet — playbook §9). These results verify the notification logic and timing, **not** a live gateway integration.

## Manual smoke test (live server)

Ran `uvicorn app.main:app` and exercised the API with curl: booked a slot (`201`), second booking of the same slot rejected (`409`), rescheduled 10:00 → 11:00 (same ID, old reminders cancelled, new ones pending), cancelled (`CANCELLED`). All as expected.

## Open defects

None.
