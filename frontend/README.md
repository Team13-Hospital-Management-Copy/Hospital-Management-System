# HMS Frontend (Next.js)

A minimal demo UI covering exactly what Sprint 1 delivered end to end:

1. **Staff login** (US-01) - `/login`
2. **Set up a doctor** (US-07) - `/doctors/new` (administrator only)
3. **Register a patient** (US-05) - `/patients/new` (receptionist only)
4. **Book an OPD appointment** (US-08) and see the booking confirmation + notification
   status (US-11) - `/appointments/book`

There is no self-service staff registration (RBAC: that's the future US-19 Staff Account
Administration story), so two demo accounts need to be seeded into the backend database
before logging in - see `backend/scripts/seed_demo_users.py`.

Sprint 2 features (diagnosis, prescriptions, billing, lab, etc.) are intentionally not in
this UI - it only covers what Sprint 1 shipped.

## Run it

1. **Backend** (from `backend/`), allowing this frontend's origin:

   ```bash
   pip install -r requirements.txt
   python -m scripts.seed_demo_users
   CORS_ALLOWED_ORIGINS=http://localhost:3000 uvicorn app.main:app --reload
   ```

2. **Frontend** (from `frontend/`):

   ```bash
   npm install
   cp .env.local.example .env.local   # points NEXT_PUBLIC_API_BASE_URL at the backend
   npm run dev
   ```

3. Open <http://localhost:3000>, sign in as `admin1` / `Admin#12345` (administrator) to set
   up a doctor, then `reception1` / `Reception#12345` (receptionist) to register a patient
   and book their appointment.

## Notes

- Auth is a bearer token from `POST /auth/login`, kept in `localStorage` for this demo only
  (see `lib/auth-context.tsx`); every API call is in `lib/api.ts`.
- Each page calls `useRequireAuth()` and redirects to `/login` if there's no session; the
  backend is still the one enforcing role checks (RBAC, US-04) - the UI not showing a button
  is a convenience, not the security boundary.
