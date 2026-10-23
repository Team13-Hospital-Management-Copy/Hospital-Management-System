# Test Results — Sprint 1 (US-02, US-07, US-08)

- **Story owner:** nisargagoudar-web (implemented with parnikahallalli)
- **Date executed:** 23 Oct 2026
- **Build:** branch `feature/us-02-07-08-doctor-booking-tls`
- **Environment:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, uvicorn 0.34, OpenSSL 3.0, SQLite
- **How to re-run:** `cd backend && pytest -v tests/test_doctors.py tests/test_opd_booking.py tests/test_tls.py`
- **Overall:** 32 / 32 passed, 0 failed. Full backend suite (all stories so far): 100 / 100 passed.

## TC-DOC — Doctor profile & availability (US-07)

**Acceptance criteria:** a doctor profile stores name, specialization, department and a configurable weekly slot schedule; schedule changes are immediately reflected in availability queries.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| DOC.1 | Admin creates a doctor with a weekly schedule | `201`, ID `DOC-000001`, profile and schedule stored | PASS |
| DOC.2 | Receptionist tries to create a doctor | `403`, denial written to audit log | PASS |
| DOC.3 | Create a doctor without logging in | `401` | PASS |
| DOC.4 | Available slots for a scheduled day (09:00–11:00, 30-min slots) | 09:00, 09:30, 10:00, 10:30 | PASS |
| DOC.5 | Available slots for an unscheduled day | Empty list | PASS |
| DOC.6 | Replace schedule with 14:00–15:00, then query availability | Only 14:00 and 14:30 straight away; change audit-logged | PASS |
| DOC.7 | Overlapping blocks / end before start | `422` | PASS |
| DOC.8 | Change department and deactivate | Saved; deactivated doctor has no slots and is hidden from the list | PASS |
| DOC.9 | Doctor-role user lists and filters doctors; unknown ID | Both doctors listed, filter by department works, `404` for unknown | PASS |

## TC-Appt-01 — Book OPD appointment (US-08, HMS-F-005)

**Acceptance criterion (AC-HMS-F-005):** booking succeeds only for an available slot and the slot is then marked unavailable.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| 01.1 | Receptionist books 09:00 for a registered patient | `201`; 09:00 no longer in available slots; booking audit-logged | PASS |
| 01.2 | Book the same slot again | `409` | PASS |
| 01.3 | Slot outside the schedule (15:00) or not on a slot boundary (09:10) | `409`, nothing stored | PASS |
| 01.4 | Unknown patient / unknown doctor / wrong department | `404` / `404` / `422` | PASS |
| 01.5 | Doctor deactivated | `409` | PASS |
| 01.6 | Patient role books; doctor role tries; no token | `201` / `403` / `401` | PASS |
| 01.7 | Booking triggers US-11 notifications | Confirmation sent, reminder queued | PASS |

## TC-Sec-01 — TLS 1.2+ for client ↔ server (US-02, HMS-SR-001)

**Acceptance criterion (AC-HMS-SR-001):** connection attempts using TLS below 1.2 or plaintext are rejected.

These tests start the real app with `app.serve` on a local port and make real TLS connections.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| Sec-01.1 | Handshake pinned to TLS 1.0 | Refused by server | PASS |
| Sec-01.2 | Handshake pinned to TLS 1.1 | Refused by server | PASS |
| Sec-01.3 | Handshake with TLS 1.2 / TLS 1.3 | Accepted | PASS |
| Sec-01.4 | Server SSL context | `minimum_version == TLSv1_2` | PASS |
| Sec-01.5 | Plain `http://` to the TLS port | Connection fails | PASS |
| Sec-01.6 | `https://` request | Reaches the app; `Strict-Transport-Security` header set | PASS |
| Sec-01.7 | Behind a proxy: `X-Forwarded-Proto: http` vs `https` | `403` vs passes through with HSTS | PASS |

For Sec-01.1/01.2 the test first proves the same client *can* negotiate TLS 1.0/1.1 with a deliberately permissive server, so the rejection really comes from our server. If a machine's OpenSSL cannot offer TLS 1.0/1.1 at all, those two cases are skipped and Sec-01.4 still covers the requirement.

Manual check with curl against `python -m app.serve`: TLS 1.3 and TLS 1.2 reached the app; `--tls-max 1.1` and plain `http://` failed.

## TC-Sec-02 — TLS for server ↔ database (US-02, HMS-NF-003)

**Acceptance criterion:** the configuration review confirms TLS 1.2+ is enforced for database connections.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| Sec-02.1 | PostgreSQL with `sslmode=verify-full` / `require` | Accepted | PASS |
| Sec-02.2 | PostgreSQL with no `sslmode` / `sslmode=prefer` | Rejected | PASS |
| Sec-02.3 | MySQL with `ssl_mode=VERIFY_IDENTITY` / without | Accepted / rejected | PASS |
| Sec-02.4 | Local SQLite file | Accepted (no network connection) | PASS |
| Sec-02.5 | App startup with an unencrypted networked DB URL | Refuses to start; `REQUIRE_DB_TLS=0` opt-out works | PASS |

**Not covered:** no real PostgreSQL/MySQL server was available, so Sec-02 checks the configuration the app enforces, not a live encrypted database session. External services (SMS/e-mail, LIS, payment) are still mocks, so their TLS must be verified when they are integrated.

## Regression

All earlier stories still pass: US-01, US-03, US-04, US-05, US-06 and US-09/10/11 (68 tests).

## Open defects

None.
