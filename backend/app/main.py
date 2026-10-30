
import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .admin import router as admin_router
from .appointments import router as appointments_router
from .auth import router as auth_router
from .booking import router as booking_router
from .consultations import router as consultations_router
from .database import Base, SessionLocal, engine
from .doctors import router as doctors_router
from .ehr import router as ehr_router
from .lab_tests import router as lab_tests_router
from .notifications import dispatch_due_notifications, get_gateway
from .notifications import router as notifications_router
from .patients import router as patients_router
from .pharmacy import router as pharmacy_router
from .prescriptions import router as prescriptions_router
from .staff_accounts import router as staff_accounts_router
from .tls import HttpsOnlyMiddleware


Base.metadata.create_all(bind=engine)

logger = logging.getLogger("hms")


async def _reminder_loop(interval_seconds: float) -> None:
    # AC-HMS-F-008: periodically send reminders that have become due (24h before each slot)
    # and retry any sends that failed.
    while True:
        try:
            with SessionLocal() as db:
                dispatch_due_notifications(db, get_gateway())
        except Exception:  # noqa: BLE001 - keep the loop alive; the next tick retries
            logger.exception("Reminder dispatch failed")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    interval = float(os.environ.get("REMINDER_DISPATCH_INTERVAL_SECONDS", "60"))
    task = asyncio.create_task(_reminder_loop(interval)) if interval > 0 else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Hospital Management System API",
    description=(
        "Team 13's secure clinical workflow API: staff login and role-based access control, "
        "patient registration, doctor scheduling, OPD appointment booking, clinical "
        "consultations, longitudinal patient EHR, and pharmacy inventory and dispensing."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Auth", "description": "Staff login, logout and session management."},
        {"name": "Patients", "description": "Patient registration, search and record lookup."},
        {
            "name": "Patient EHR",
            "description": (
                "Chronological patient consultation history, prescriptions, "
                "and laboratory results."
            ),
        },
        {"name": "Doctors", "description": "Doctor profiles, schedules and slot availability."},
        {
            "name": "Appointments",
            "description": "Booking, rescheduling and cancelling appointments.",
        },
        {
            "name": "Consultations",
            "description": "Clinical diagnoses, vital signs, and consultation notes.",
        },
        {
            "name": "Lab Tests",
            "description": "Ordering laboratory/radiology tests and recording their results.",
        },
        {
            "name": "Pharmacy",
            "description": (
                "Medicine batch inventory, dispensing, stock decrement, "
                "low-stock flags, and expiry alerts."
            ),
        },
        {
            "name": "Notifications",
            "description": "Appointment confirmations and reminders.",
        },
        {"name": "Admin", "description": "Administrative and audit-log endpoints."},
        {
            "name": "Staff Administration",
            "description": "Create, modify and deactivate staff accounts and roles.",
        },
    ],
    lifespan=lifespan,
)

app.add_middleware(HttpsOnlyMiddleware)

# The Next.js frontend runs on a different origin in development.
# Override using CORS_ALLOWED_ORIGINS (comma-separated) when required.
_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(booking_router)
app.include_router(appointments_router)
app.include_router(notifications_router)
app.include_router(patients_router)
app.include_router(ehr_router)
app.include_router(doctors_router)
app.include_router(consultations_router)
app.include_router(lab_tests_router)
app.include_router(pharmacy_router)
app.include_router(prescriptions_router)
app.include_router(staff_accounts_router)
