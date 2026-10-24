# HMS Backend

Minimal FastAPI backend. Currently implements:

- **US-01: Secure Staff Login with Account Lockout** (HMS-F-004, HMS-SR-004, HMS-SR-006)
- **US-02: Enforce TLS 1.2+ Secure Communication** (HMS-SR-001, HMS-NF-003)
- **US-03: Session Timeout & Secure Logout** (HMS-SR-005)
- **US-04: Role-Based Access Control (RBAC) Enforcement** (HMS-SR-002)
- **US-09: Prevent Double-Booking of Appointment Slots** (HMS-F-006)
- **US-10: Reschedule or Cancel Appointment** (HMS-F-007)
- **US-11: Appointment Confirmation & Reminder Notifications** (HMS-F-008)

## Setup

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On Linux or macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run

For local development, start the application with Uvicorn:

```bash
uvicorn app.main:app --reload
```

This starts the application over HTTP. It is intended for local development and does not enable HTTPS.

By default, the application uses a local SQLite database file (`hms.db`). Set `DATABASE_URL` to point at a real RDBMS (e.g. `postgresql://user:pass@host/dbname`) for anything beyond local development, per SRS §3.3.

## Secure HTTPS startup (US-02)

For secure incoming client-server communication, the project provides a separate Hypercorn startup script. Hypercorn configures its TLS context to require TLS 1.2 or newer.

The server requires a TLS certificate and its corresponding private key before it can start.

Set the following environment variables to the paths of your certificate and private key:

- `TLS_CERTFILE`: Path to the TLS certificate file.
- `TLS_KEYFILE`: Path to the corresponding private key file.

PowerShell example, assuming the certificate files exist at the specified paths:

```powershell
$env:TLS_CERTFILE = "certs/server.crt"
$env:TLS_KEYFILE = "certs/server.key"
python -m app.secure_server
```

The secure server is configured to listen on port `8443`.

These example certificate paths are placeholders. You must obtain or generate appropriate certificate and key files before starting the secure server. Do not commit private keys or production certificates to the repository.

The regular Uvicorn development command does not enable TLS. Use the secure startup path when testing HTTPS.

### Database connections

The default SQLite database is a local file and does not use a network connection, so TLS is not applicable to that connection.

For a remote database, TLS must be configured separately using the appropriate database driver and server settings. The current database configuration does not itself enforce TLS for remote database connections. Before production deployment, configure certificate verification and require encrypted database connections according to the database driver's documentation.

### External services

The notification gateway currently uses `MockNotificationGateway`. Messages are logged and stored rather than sent through a real external SMS or email provider. TLS configuration for an external notification service must be implemented and verified when a real provider is integrated.

## Test

Run the test suite from the backend directory:

```bash
python -m pytest -v
```

## Endpoints

- `POST /auth/login` — Accepts `{"username": "...", "password": "..."}`. Locks the account after five consecutive failed attempts and records login outcomes, including success, failure, lockout, and attempts on an already locked account, in an audit log table. On success, returns a bearer `token` alongside `status` and `message`.
- `POST /auth/logout` — Accepts an optional `Authorization: Bearer <token>` header. Deletes the session token immediately; reusing it afterward returns `401`. Calling it without a token or with an already invalid token still returns `200` (AC-HMS-SR-005).
- `GET /admin/audit-log` — Requires an `Authorization: Bearer <token>` header from a user whose role is `ADMINISTRATOR` or `SYSTEM_ADMINISTRATOR`. Returns the most recent 200 audit log entries. A receptionist or pharmacist token receives `403`, and the denial is audit-logged (AC-HMS-SR-002).

### Session timeout (US-03)

Every authenticated request that goes through `get_current_user`, including requests protected by `require_role(...)`, refreshes the token's `last_seen_at`.

If more than 10 minutes pass between requests, the next request returns `401` and the token is deleted server-side. The client must log in again.

This is a **sliding idle timeout**, not a fixed session lifetime: staying active keeps the session alive indefinitely.

### Roles

Six roles are defined in `app/roles.py` according to SRS §2.3:

- `PATIENT`
- `DOCTOR`
- `RECEPTIONIST`
- `PHARMACIST`
- `ADMINISTRATOR`
- `SYSTEM_ADMINISTRATOR`

A `User` defaults to `RECEPTIONIST` if no role is set at creation.

### Appointments (US-09, US-10, US-11)

All appointment times are UTC. A `slot_start` with a timezone offset (e.g. `+05:30`) is converted to UTC first.

- `POST /appointments` — Accepts `{"patient_uhid": "...", "doctor_id": "...", "slot_start": "2026-10-21T10:00:00Z"}`. Returns `201` with the appointment, or `409` if that doctor's slot is already booked. Sends the confirmation immediately and queues a reminder for 24 hours before the slot.

  **Temporary:** This is a minimal booking endpoint so the lifecycle stories can be tested before US-08 merges. US-08's booking endpoint should call `app.appointments.book_appointment()` and replace it.
- `GET /appointments/booked-slots?doctor_id=DOC-1&day=2026-10-21` — Returns slots already taken that day.
- `GET /appointments/{id}` — Returns one appointment.
- `POST /appointments/{id}/cancel` — Cancels an appointment and frees the slot. Returns `400` inside the cutoff window, `409` if already cancelled, and `404` if unknown.
- `POST /appointments/{id}/reschedule` — Accepts `{"new_slot_start": "..."}`. Moves the same booking rather than creating a duplicate row, and frees the old slot. Returns `409` if the new slot is taken and `400` inside the cutoff window.
- `GET /appointments/{id}/notifications` — Returns the appointment's confirmation, reminder, and cancellation notifications and their statuses.
- `POST /notifications/dispatch-due` — Dispatches due reminders and retries failed sends. The server also runs this process automatically in the background.

**How double-booking is prevented (US-09):** A partial unique index on `(doctor_id, slot_start)` covers only `BOOKED` rows. The database rejects a second simultaneous booking for the same doctor's slot, making the protection safe under concurrency rather than relying only on a check in Python. Cancelled rows are excluded, allowing cancelled slots to be booked again.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./hms.db` | Database connection URL. Remote database TLS must be configured separately. |
| `TLS_CERTFILE` | Not set | Path to the TLS certificate used by the secure Hypercorn server. |
| `TLS_KEYFILE` | Not set | Path to the corresponding TLS private key. |
| `APPOINTMENT_CHANGE_CUTOFF_HOURS` | `2` | Rescheduling or cancellation is refused when the slot is closer than this many hours (US-10). |
| `NOTIFICATION_CHANNELS` | `SMS,EMAIL` | Channels used for each notification (US-11). |
| `REMINDER_DISPATCH_INTERVAL_SECONDS` | `60` | How often the background job sends due reminders; `0` disables it. |

## Known limitations / out of scope

- **TLS (US-02):** The secure Hypercorn startup path configures TLS 1.2 as the minimum version for incoming HTTPS connections. End-to-end HTTPS still requires a valid certificate and key and must be tested. The regular Uvicorn development command does not enable TLS.
- **Remote database TLS:** The current database configuration does not enforce TLS for remote database connections. This must be configured and verified separately for the chosen database driver before production deployment.
- **External-service TLS:** Notifications use `MockNotificationGateway`. Messages are logged and stored, not actually delivered, because no SMS/email gateway is integrated yet. TLS requirements for an external notification provider remain pending integration. A real gateway can be integrated by overriding the `get_gateway` dependency.
- No user-creation endpoint yet. Test and seed users must be inserted directly (see `tests/conftest.py`); staff account creation is HMS-F-019 (Staff Account & Role Administration).
- Account unlock requires a direct database update for now; the admin-assisted recovery process is part of HMS-F-019.
- Only `/admin/audit-log` is currently protected by a role check because it is the only sensitive endpoint implemented so far. `/auth/login` is intentionally public so users can obtain a token. Future endpoints for patient records, billing, prescriptions, and other sensitive functions must apply `require_role(...)` individually; RBAC is not retroactive.
- Until US-05 (Patient Registration) exposes phone and email details, notifications are addressed to the patient's UHID.
- If a booking is made less than 24 hours ahead, only the confirmation is sent; no separate reminder is queued.
- The appointment change cutoff is controlled by an environment variable. Making it admin-editable in the UI belongs with US-19.
- Appointment and notification endpoints do not yet apply `require_role(...)`. The RBAC mechanism exists (US-04), but it has not yet been wired into `appointments.py` and `notifications.py`; these endpoints are also not protected by the US-03 idle timeout, which applies only to requests that go through `get_current_user`.
- The idle timeout is per token, not account-wide. Logging in on a second device creates a second token with its own timeout clock. The same account can have multiple concurrent sessions.
