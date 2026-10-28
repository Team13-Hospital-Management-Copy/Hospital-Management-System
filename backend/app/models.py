from datetime import date, datetime, time, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .roles import RECEPTIONIST


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default=RECEPTIONIST)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class AuthToken(Base):
    """Bearer session. last_seen_at drives the HMS-SR-005 idle timeout (US-03)."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    event_type: Mapped[str] = mapped_column(String(50))
    username: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(String(500), default="")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uhid: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


# --- Appointment lifecycle (US-09, US-10, US-11) -----------------------------

APPOINTMENT_STATUS_BOOKED = "BOOKED"
APPOINTMENT_STATUS_CANCELLED = "CANCELLED"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_appointments_active_doctor_slot",
            "doctor_id",
            "slot_start",
            unique=True,
            sqlite_where=text("status = 'BOOKED'"),
            postgresql_where=text("status = 'BOOKED'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_uhid: Mapped[str] = mapped_column(String(64), index=True)
    doctor_id: Mapped[str] = mapped_column(String(64), index=True)
    slot_start: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default=APPOINTMENT_STATUS_BOOKED)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rescheduled_count: Mapped[int] = mapped_column(Integer, default=0)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(10))
    recipient: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(String(1000))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), default="")


# --- Doctor management (US-07) -----------------------------------------------


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    specialization: Mapped[str] = mapped_column(String(100), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class DoctorScheduleBlock(Base):
    __tablename__ = "doctor_schedule_blocks"
    __table_args__ = (
        UniqueConstraint(
            "doctor_pk",
            "weekday",
            "start_time",
            name="uq_schedule_block_start",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_pk: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


# --- Consultations ------------------------------------------------------------


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), unique=True, index=True
    )
    patient_uhid: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.uhid"), index=True
    )
    diagnosis: Mapped[str] = mapped_column(String(200), nullable=False)
    blood_pressure: Mapped[str | None] = mapped_column(String(20), nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pulse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spo2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clinical_notes: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )


# --- Electronic prescriptions (US-13) ----------------------------------------


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Link the prescription to the correct patient and consultation.
    patient_uhid: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.uhid"), index=True
    )
    consultation_id: Mapped[int] = mapped_column(
        ForeignKey("consultations.id"), index=True
    )

    # Record which doctor created the prescription.
    doctor_username: Mapped[str] = mapped_column(String(255), nullable=False)

    # Required medication details.
    drug_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    duration: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )


# --- Lab/radiology test orders (US-14) ---------------------------------------

LAB_TEST_STATUS_ORDERED = "ORDERED"
LAB_TEST_STATUS_COMPLETED = "COMPLETED"


class LabTestOrder(Base):
    """AC-HMS-F-011: a test order moves Ordered -> Completed with results attached."""

    __tablename__ = "lab_test_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), index=True
    )
    patient_uhid: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.uhid"), index=True
    )
    test_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=LAB_TEST_STATUS_ORDERED)
    ordered_by: Mapped[str] = mapped_column(String(255), nullable=False)
    result: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --- Pharmacy inventory and dispensing (US-18) -------------------------------


class MedicineBatch(Base):
    """A medicine batch with its available stock and expiry date."""

    __tablename__ = "medicine_batches"
    __table_args__ = (
        UniqueConstraint(
            "medicine_name",
            "batch_number",
            name="uq_medicine_batch",
        ),
        Index("ix_medicine_batches_expiry_date", "expiry_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    medicine_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    batch_number: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )


class PharmacyDispenseRecord(Base):
    """Records each quantity dispensed from a medicine batch to a patient."""

    __tablename__ = "pharmacy_dispense_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("medicine_batches.id"), index=True, nullable=False
    )
    patient_uhid: Mapped[str] = mapped_column(
        ForeignKey("patients.uhid"), index=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    dispensed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: _utcnow().replace(tzinfo=None)
    )
