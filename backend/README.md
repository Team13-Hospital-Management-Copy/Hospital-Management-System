# HMS Backend

Minimal FastAPI backend. Currently implements:

- **US-01: Secure Staff Login with Account Lockout** (HMS-F-004, HMS-SR-004, HMS-SR-006)
- **US-02: Enforce TLS 1.2+ Secure Communication** (HMS-SR-001, HMS-NF-003)
- **US-03: Session Timeout & Secure Logout** (HMS-SR-005)
- **US-04: Role-Based Access Control (RBAC) Enforcement** (HMS-SR-002)
- **US-09: Prevent Double-Booking of Appointment Slots** (HMS-F-006)
- **US-10: Reschedule or Cancel Appointment** (HMS-F-007)
- **US-11: Appointment Confirmation & Reminder Notifications** (HMS-F-008)
- **US-06: Patient Search & Record Retrieval** (HMS-F-002)
- **US-07: Doctor Profile & Availability Management** (supports HMS-F-005, HMS-F-006)
- **US-08: Book OPD Appointment with Real-Time Slot Availability** (HMS-F-005)

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

By default this uses a local SQLite file (`hms.db`). Set `DATABASE_URL` to point at a real
RDBMS (e.g. `postgresql://user:pass@host/dbname?sslmode=verify-full`) for anything beyond local
development, per SRS §3.3. A networked database URL must force TLS or the app refuses to start
(US-02, see below).

### Run over HTTPS (TLS 1.2+, US-02)

```bash
python -m app.serve --certfile cert.pem --keyfile key.pem --host 0.0.0.0 --port 8443
```

This serves HTTPS only: handshakes below TLS 1.2 and plaintext HTTP are refused, and every response
carries an HSTS header. For a quick local try-out you can use the **test-only** certificate in
`tests/fixtures/` (self-signed; never use it for a real deployment).

## Test

```bash
pytest -v
```

## Endpoints

- `POST /auth/login` — `{"username": "...", "password": "..."}`. Locks the account after 5
  consecutive failed attempts and records every login outcome (success, failure, lockout, or a
  blocked attempt on an already-locked account) to an audit log table. On success, returns a
  bearer `token` alongside `status`/`message`.
- `POST /auth/logout` — `Authorization: Bearer <token>` (optional). Deletes the session token
  immediately; reusing it afterward gets `401`. Idempotent: calling it with no token, or an
  already-invalid one, still returns `200` (AC-HMS-SR-005).
- `GET /admin/audit-log` — requires `Authorization: Bearer <token>` from a user whose role is
  `ADMINISTRATOR` or `SYSTEM_ADMINISTRATOR`. Returns the most recent 200 audit log entries.
  Serves as the concrete example endpoint proving role enforcement works; a receptionist or
  pharmacist token gets `403` and the denial itself is audit-logged (AC-HMS-SR-002).

### Session timeout (US-03)

Every authenticated request (anything going through `get_current_user`, i.e. anything behind
`require_role(...)`) refreshes the token's `last_seen_at`. If more than 10 minutes pass between
requests, the next one gets `401` and the token is deleted server-side — the client must log in
again. This is a **sliding** idle timeout, not a fixed session lifetime: staying active keeps the
session alive indefinitely.

### Roles

Six roles per SRS §2.3, defined in `app/roles.py`: `PATIENT`, `DOCTOR`, `RECEPTIONIST`,
`PHARMACIST`, `ADMINISTRATOR`, `SYSTEM_ADMINISTRATOR`. A `User` defaults to `RECEPTIONIST` if no
role is set at creation.

### Appointments (US-09, US-10, US-11)

All times are UTC. A `slot_start` with a timezone offset (e.g. `+05:30`) is converted to UTC first.

- `POST /appointments` — `{"patient_uhid": "...", "doctor_id": "...", "slot_start": "2026-10-21T10:00:00Z"}`.
  Returns `201` with the appointment, or `409` if that doctor's slot is already booked. Sends the
  confirmation immediately and queues a reminder for 24h before the slot. This is the low-level
  booking call: it does not check that the patient/doctor exist or that the slot is on the doctor's
  schedule. Front ends should use `POST /appointments/opd` (US-08) instead.
- `GET /appointments/booked-slots?doctor_id=DOC-1&day=2026-10-21` — slots already taken that day.
- `GET /appointments/{id}` — one appointment.
- `POST /appointments/{id}/cancel` — cancels and frees the slot. `400` inside the cutoff window,
  `409` if already cancelled, `404` if unknown.
- `POST /appointments/{id}/reschedule` — `{"new_slot_start": "..."}`. Moves the same booking (no
  duplicate row) and frees the old slot. `409` if the new slot is taken, `400` inside the cutoff.
- `GET /appointments/{id}/notifications` — every confirmation/reminder/cancellation and its status.
- `POST /notifications/dispatch-due` — sends due reminders and retries failed sends. The server also
  does this automatically in the background.

**How double-booking is prevented (US-09):** a partial unique index on `(doctor_id, slot_start)`
covering only `BOOKED` rows. The database itself rejects the second of two simultaneous bookings, so
it is safe under concurrency (not just a "check then insert" in Python). Cancelled rows are excluded,
which is what makes a cancelled slot bookable again.

### Doctors (US-07)

Writes need an `ADMINISTRATOR` or `SYSTEM_ADMINISTRATOR` token; reads need any logged-in user.
Doctor IDs are generated like UHIDs: `DOC-000001`, `DOC-000002`, ...

- `POST /doctors` — `{"full_name", "specialization", "department", "slot_minutes": 15, "schedule": [...]}`.
  `schedule` is the weekly OPD timetable: a list of `{"weekday": 0-6 (0 = Monday), "start_time": "09:00",
  "end_time": "13:00"}` blocks (UTC, like all slots). Overlapping blocks on the same day are rejected (`422`).
- `GET /doctors?department=&specialization=` — active doctors (add `include_inactive=true` for all).
- `GET /doctors/{doctor_id}` — one doctor with their schedule.
- `PATCH /doctors/{doctor_id}` — change name/specialization/department/slot length, or set
  `"is_active": false` to stop new bookings.
- `PUT /doctors/{doctor_id}/schedule` — replace the whole weekly schedule.
- `GET /doctors/{doctor_id}/available-slots?day=2026-10-30` — free, future slots that day. Worked out
  live from the current schedule and bookings, so schedule changes and new bookings show up immediately.

Creating, updating and rescheduling doctors is written to the audit log.

### OPD booking (US-08)

- `POST /appointments/opd` — `RECEPTIONIST` or `PATIENT` token.
  `{"patient_uhid": "HMS-000001", "doctor_id": "DOC-000001", "department": "Cardiology" (optional), "slot_start": "2026-10-30T09:00:00Z"}`.

Checks, in order: the patient is registered (`404`), the doctor exists (`404`) and is active (`409`),
the doctor is in the chosen department (`422`), and the slot is one the doctor's schedule offers
(`409`). It then calls `book_appointment()` (US-09), so double-booking protection and the US-11
confirmation/reminder apply automatically. A booked slot disappears from `available-slots`
(AC-HMS-F-005). Each booking is audit-logged with the user who made it.

### Patient search (US-06)

`GET /patients/search` finds patients by exactly one of `uhid`, `name` or `phone` (HMS-F-002,
AC-HMS-F-002). Requires `Authorization: Bearer <token>` from a `RECEPTIONIST` or `DOCTOR`; other
roles get `403`, and a missing or invalid token gets `401`.

- Matching is a partial, case-insensitive "contains" match on the chosen field. Input is trimmed
  first; `%` and `_` in the input are matched literally, not as wildcards.
- Phone numbers are matched as stored (no digit normalisation), so search with the digits as they
  were entered at registration.
- Results are ordered by UHID and capped at 50 patients per request.
- No match returns `200` with an empty list.

Request:

```
GET /patients/search?name=lakshmi
Authorization: Bearer <token>
```

Response `200`:

```json
[
  {
    "id": 1,
    "uhid": "HMS-000001",
    "full_name": "Lakshmi Narayan",
    "age": 45,
    "gender": "Female",
    "phone": "9876543210",
    "address": "12 Park Road"
  }
]
```

Errors:

| Status | When | `detail` |
| --- | --- | --- |
| `401` | No or invalid bearer token. | `Missing or invalid session token.` |
| `403` | Token belongs to a role other than receptionist or doctor. | `You do not have permission to access this resource.` |
| `422` | No key, more than one key, a blank value, or a value over the field's length (`uhid` 20, `name` 150, `phone` 20). | `Provide exactly one of uhid, name or phone.` / `Search value cannot be empty.` / a validation error |

`GET /patients/{uhid}` (US-05) still returns the single patient by exact UHID. It does not yet
apply `require_role(...)`, so it is not covered by the role check above.

### Secure communication (US-02)

- **Client ↔ server:** `python -m app.serve` uses an SSL context with `minimum_version = TLSv1_2`
  (`app/tls.py`), so TLS 1.0/1.1 and plaintext connections fail the handshake.
- **Behind a proxy/load balancer:** if TLS is terminated in front of the app, run with
  `ENFORCE_HTTPS=1 TRUST_PROXY_HEADERS=1`. Requests whose `X-Forwarded-Proto` is not `https` get
  `403 HTTPS (TLS 1.2 or higher) is required.` Configure the proxy itself for TLS 1.2+ as well.
- **Server ↔ database:** at startup `DATABASE_URL` is checked. A PostgreSQL URL must use
  `sslmode=require|verify-ca|verify-full` (prefer `verify-full`); a MySQL URL must use
  `ssl_mode=REQUIRED|VERIFY_CA|VERIFY_IDENTITY` or `ssl_ca`. Otherwise the app refuses to start.
  Local SQLite files are allowed (no network connection).

### Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `APPOINTMENT_CHANGE_CUTOFF_HOURS` | `2` | Reschedule/cancel is refused when the slot is closer than this (US-10). |
| `NOTIFICATION_CHANNELS` | `SMS,EMAIL` | Channels each notification is sent on (US-11). |
| `REMINDER_DISPATCH_INTERVAL_SECONDS` | `60` | How often the background job sends due reminders; `0` disables it. |
| `ENFORCE_HTTPS` | `0` (`1` under `app.serve`) | Reject plaintext HTTP requests and send HSTS (US-02). |
| `TRUST_PROXY_HEADERS` | `0` | Use `X-Forwarded-Proto` from a TLS-terminating proxy (US-02). |
| `REQUIRE_DB_TLS` | `1` | Refuse a networked `DATABASE_URL` that doesn't force TLS. `0` only for a throwaway local DB (US-02). |

## Known limitations / out of scope

- No user-creation endpoint yet. Test/seed users must be inserted directly (see
  `tests/conftest.py`); staff account creation is HMS-F-019 (Staff Account & Role Administration).
- Account unlock requires a direct database update for now; the admin-assisted recovery process
  is part of HMS-F-019.
- Only one endpoint (`/admin/audit-log`) is actually behind a role check today, because it's the
  only sensitive endpoint that exists yet. `/auth/login` is intentionally public (you can't
  authenticate your way into getting a token). Every endpoint added by future stories (patient
  records, billing, prescriptions, etc.) needs to apply `require_role(...)` itself — RBAC isn't
  retroactive.
- TLS for external services (SMS/e-mail gateway, LIS, payment gateway) must be checked when those
  integrations are built; they are still mocks today.
- `uvicorn app.main:app` (plain HTTP) is still the quickest way to develop locally; use
  `python -m app.serve` for anything that handles real data.
- **Notifications use a mock gateway** (`MockNotificationGateway`): messages are logged and stored,
  not actually delivered, because no SMS/e-mail gateway is available yet (playbook §9 risk for US-11).
  Plug in a real one by overriding the `get_gateway` dependency.
- Until US-05 (Patient Registration) exposes phone/e-mail, notifications are addressed to the
  patient's UHID.
- If a booking is made less than 24h ahead, only the confirmation is sent (no separate reminder).
- The cutoff is set by environment variable; making it admin-editable in the UI belongs with US-19.
- Appointment and notification endpoints do not yet apply `require_role(...)` — the RBAC
  mechanism exists (US-04), but nobody has wired it into `appointments.py`/`notifications.py`
  yet, so they're also not behind the US-03 idle timeout (which only applies to requests that
  go through `get_current_user`).
- The idle timeout is per-token, not account-wide: logging in on a second device gets a second
  token with its own clock. Nothing stops the same account from having many concurrent sessions.
