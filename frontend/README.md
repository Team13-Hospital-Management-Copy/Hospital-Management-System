# HMS Frontend (Next.js)

Demo UI covering what Sprint 1 and Sprint 2 delivered end to end. After login, the dashboard
groups every screen by who uses it:

**Front desk**

- **Register a patient** (US-05) - `/patients/new`
- **Book an OPD appointment** (US-08) with the booking confirmation and notifications (US-11) -
  `/appointments/book`
- **Reschedule or cancel** (US-09 / US-10) - `/appointments/manage`
- **Billing** (US-17) - `/billing`: open a bill for a visit, pull in its consultation, lab tests,
  medicines and bed days at tariff prices, apply a discount scheme, take payments and show the
  receipt. A second tab is the administrators' price list and discount schemes.
- **Admission & discharge** (US-16) - `/inpatient`: bed map, admit, discharge, print summary

**Clinical**

- **Doctor's workspace** - `/clinical`: consultation and vitals (US-12), prescriptions (US-13),
  ordering and recording lab tests (US-14), and the patient's full visit history (US-15)
- **Pharmacy** - `/pharmacy`: a patient's prescriptions, dispensing from a batch, receiving
  stock, low-stock and expiry alerts

**Administration**

- **Set up a doctor** (US-07) - `/doctors/new`
- **Staff accounts** (US-19) - `/admin/staff`
- **Operational reports** (US-20) - `/admin/reports`, with PDF/CSV download

Staff accounts beyond the first administrator are created from `/admin/staff` (US-19). For a
quick demo, `backend/scripts/seed_demo_users.py` seeds one account per role.

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

3. Open <http://localhost:3000> and sign in with a demo account:

   | Account | Password | Role | Use it for |
   | --- | --- | --- | --- |
   | `admin1` | `Admin#12345` | Administrator | doctors, staff, prices & schemes, reports |
   | `reception1` | `Reception#12345` | Receptionist | patients, appointments, billing, admissions |
   | `doctor1` | `Doctor#12345` | Doctor | consultations, prescriptions, lab tests, patient record |
   | `pharmacist1` | `Pharmacist#12345` | Pharmacist | dispensing and stock |

   A full walk-through: admin sets up a doctor and the price list → reception registers a
   patient and books them → doctor records the consultation, prescribes and orders tests →
   pharmacist dispenses → reception opens a bill for the appointment, pulls in the visit
   charges, applies a scheme and takes payment.

## Notes

- Auth is a bearer token from `POST /auth/login`, kept in `localStorage` for this demo only
  (see `lib/auth-context.tsx`); every API call is in `lib/api.ts`.
- The UI shows every screen to every signed-in user (login doesn't return the role); the
  backend refuses anything the role isn't allowed to do and the page shows that error.
- Each page calls `useRequireAuth()` and redirects to `/login` if there's no session; the
  backend is still the one enforcing role checks (RBAC, US-04) - the UI not showing a button
  is a convenience, not the security boundary.
