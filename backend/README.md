# HMS Backend

Minimal FastAPI backend. Currently implements:

- **US-01: Secure Staff Login with Account Lockout** (HMS-F-004, HMS-SR-004, HMS-SR-006)
- **US-04: Role-Based Access Control (RBAC) Enforcement** (HMS-SR-002)
- **US-09: Prevent Double-Booking of Appointment Slots** (HMS-F-006)
- **US-10: Reschedule or Cancel Appointment** (HMS-F-007)
- **US-11: Appointment Confirmation & Reminder Notifications** (HMS-F-008)

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
RDBMS (e.g. `postgresql://user:pass@host/dbname`) for anything beyond local development, per
SRS §3.3.

## Test

```bash
pytest -v
```

## Endpoints

- `POST /auth/login` — `{"username": "...", "password": "..."}`. Locks the account after 5
  consecutive failed attempts and records every login outcome (success, failure, lockout, or a
  blocked attempt on an already-locked account) to an audit log table. On success, returns a
  bearer `token` alongside `status`/`message`.
- `GET /admin/audit-log` — requires `Authorization: Bearer <token>` from a user whose role is
  `ADMINISTRATOR` or `SYSTEM_ADMINISTRATOR`. Returns the most recent 200 audit log entries.
  Serves as the concrete example endpoint proving role enforcement works; a receptionist or
  pharmacist token gets `403` and the denial itself is audit-logged (AC-HMS-SR-002).

### Roles

Six roles per SRS §2.3, defined in `app/roles.py`: `PATIENT`, `DOCTOR`, `RECEPTIONIST`,
`PHARMACIST`, `ADMINISTRATOR`, `SYSTEM_ADMINISTRATOR`. A `User` defaults to `RECEPTIONIST` if no
role is set at creation.

### Appointments (US-09, US-10, US-11)

All times are UTC. A `slot_start` with a timezone offset (e.g. `+05:30`) is converted to UTC first.

- `POST /appointments` — `{"patient_uhid": "...", "doctor_id": "...", "slot_start": "2026-10-21T10:00:00Z"}`.
  Returns `201` with the appointment, or `409` if that doctor's slot is already booked. Sends the
  confirmation immediately and queues a reminder for 24h before the slot. *Temporary:* this is a
  minimal booking endpoint so the lifecycle stories can be tested before US-08 merges; US-08's
  booking endpoint should call `app.appointments.book_appointment()` and replace it.
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

### Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `APPOINTMENT_CHANGE_CUTOFF_HOURS` | `2` | Reschedule/cancel is refused when the slot is closer than this (US-10). |
| `NOTIFICATION_CHANNELS` | `SMS,EMAIL` | Channels each notification is sent on (US-11). |
| `REMINDER_DISPATCH_INTERVAL_SECONDS` | `60` | How often the background job sends due reminders; `0` disables it. |

## Known limitations / out of scope

- No user-creation endpoint yet. Test/seed users must be inserted directly (see
  `tests/conftest.py`); staff account creation is HMS-F-019 (Staff Account & Role Administration).
- Account unlock requires a direct database update for now; the admin-assisted recovery process
  is part of HMS-F-019.
- **The login token has no expiry or idle timeout.** US-04 needed *some* notion of identity for
  role checks to check against, so a minimal bearer token is issued at login — but the 10-minute
  idle timeout and secure logout are HMS-SR-005 (Session Timeout & Secure Logout / US-03), not
  built here. Treat the current token as long-lived until US-03 lands.
- Only one endpoint (`/admin/audit-log`) is actually behind a role check today, because it's the
  only sensitive endpoint that exists yet. `/auth/login` is intentionally public (you can't
  authenticate your way into getting a token). Every endpoint added by future stories (patient
  records, billing, prescriptions, etc.) needs to apply `require_role(...)` itself — RBAC isn't
  retroactive.
- TLS enforcement (HMS-SR-001) is a deployment/infrastructure concern, not application code.
- **Notifications use a mock gateway** (`MockNotificationGateway`): messages are logged and stored,
  not actually delivered, because no SMS/e-mail gateway is available yet (playbook §9 risk for US-11).
  Plug in a real one by overriding the `get_gateway` dependency.
- Until US-05 (Patient Registration) exposes phone/e-mail, notifications are addressed to the
  patient's UHID.
- If a booking is made less than 24h ahead, only the confirmation is sent (no separate reminder).
- The cutoff is set by environment variable; making it admin-editable in the UI belongs with US-19.
- Appointment and notification endpoints do not yet apply `require_role(...)` — the RBAC
  mechanism exists (US-04), but nobody has wired it into `appointments.py`/`notifications.py`
  yet. They're also not behind the session timeout, since that's still US-03.
