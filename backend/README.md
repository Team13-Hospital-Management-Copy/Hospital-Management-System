# HMS Backend

Minimal FastAPI backend. Currently implements:

- **US-01: Secure Staff Login with Account Lockout** (HMS-F-004, HMS-SR-004, HMS-SR-006)
- **US-04: Role-Based Access Control (RBAC) Enforcement** (HMS-SR-002)

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
