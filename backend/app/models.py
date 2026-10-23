from datetime import datetime, time, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Time, UniqueConstraint, text
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
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuthToken(Base):
    """Bearer session. last_seen_at drives the HMS-SR-005 idle timeout (US-03).

    Stored as naive UTC (not DateTime(timezone=True)) to match the convention used for
    Appointment/Notification: SQLite drops tzinfo on read-back, so a timezone-aware column
    compared against datetime.now(timezone.utc) raises TypeError. Naive UTC throughout sidesteps
    that on both SQLite and a production RDBMS.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: _utcnow().replace(tzinfo=None))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: _utcnow().replace(tzinfo=None))


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# --- Appointment lifecycle (US-09, US-10, US-11) -------------------------------------------
#
# The appointment record follows the shape agreed for Sprint 1 (patient UHID, doctor ID, slot,
# status). Datetimes are stored as naive UTC so comparisons behave the same on SQLite and on a
# production RDBMS.

APPOINTMENT_STATUS_BOOKED = "BOOKED"
APPOINTMENT_STATUS_CANCELLED = "CANCELLED"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # AC-HMS-F-006: at most one *active* booking per doctor per slot. Enforced by the database
        # (not just application code) so concurrent requests cannot both succeed. Cancelled rows are
        # excluded, which is what lets a cancelled slot be booked again (AC-HMS-F-007).
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: _utcnow().replace(tzinfo=None))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rescheduled_count: Mapped[int] = mapped_column(Integer, default=0)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # CONFIRMATION | REMINDER | CANCELLATION
    channel: Mapped[str] = mapped_column(String(10))  # SMS | EMAIL
    recipient: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(String(1000))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|SENT|FAILED|CANCELLED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), default="")


# --- Doctor management (US-07) ---------------------------------------------------------------


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Public identifier used everywhere else (e.g. Appointment.doctor_id), like the patient UHID.
    doctor_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    specialization: Mapped[str] = mapped_column(String(100), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    # Length of one bookable OPD slot. Slots are generated from the weekly schedule in these steps.
    slot_minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DoctorScheduleBlock(Base):
    """One block of a doctor's weekly OPD schedule, e.g. Monday 09:00-13:00 (UTC, like all slots)."""

    __tablename__ = "doctor_schedule_blocks"
    __table_args__ = (UniqueConstraint("doctor_pk", "weekday", "start_time", name="uq_schedule_block_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_pk: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
