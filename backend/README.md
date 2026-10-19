# HMS Backend

Minimal FastAPI backend. Currently implements **US-01: Secure Staff Login with Account Lockout**
(HMS-F-004, HMS-SR-004, HMS-SR-006).

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
  blocked attempt on an already-locked account) to an audit log table.

## Known limitations / out of scope for this story

- No user-creation endpoint yet. Test/seed users must be inserted directly (see
  `tests/conftest.py`); staff account creation is HMS-F-019 (Staff Account & Role Administration).
- Account unlock requires a direct database update for now; the admin-assisted recovery process
  is part of HMS-F-019.
- Session issuance (what happens after a successful login) and the 10-minute idle timeout are
  HMS-SR-005 (Session Timeout & Secure Logout), not yet implemented.
- Role-based access control (HMS-SR-002) is not yet implemented; this endpoint only authenticates.
- TLS enforcement (HMS-SR-001) is a deployment/infrastructure concern, not application code.
