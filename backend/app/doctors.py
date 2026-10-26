from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from .appointments import booked_slots, to_utc_naive
from .database import get_db
from .models import AuditLogEntry, Doctor, DoctorScheduleBlock, User
from .notifications import utcnow
from .rbac import get_current_user, require_role
from .roles import ADMINISTRATOR, SYSTEM_ADMINISTRATOR
from .schemas import AvailableSlots, DoctorCreate, DoctorOut, DoctorUpdate, ScheduleBlock

router = APIRouter(prefix="/doctors", tags=["Doctors"])

# US-07: only administrators maintain doctor profiles and schedules (SRS §2.3, SAD §3.4).
DOCTOR_ADMIN_ROLES = (ADMINISTRATOR, SYSTEM_ADMINISTRATOR)

DOCTOR_NOT_FOUND_MESSAGE = "Doctor not found."

# A concurrent creation can compute the same "next" doctor_id before either commits; retry with a
# freshly generated one rather than failing the second request outright (same issue as, and same
# fix as, generate_uhid in patients.py).
MAX_DOCTOR_ID_GENERATION_ATTEMPTS = 5


def generate_doctor_id(db: Session) -> str:
    last = db.query(Doctor).order_by(Doctor.id.desc()).first()
    return f"DOC-{(1 if last is None else last.id + 1):06d}"


def get_doctor_or_404(db: Session, doctor_id: str) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).one_or_none()
    if doctor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DOCTOR_NOT_FOUND_MESSAGE)
    return doctor


def _schedule_blocks(db: Session, doctor: Doctor) -> list[DoctorScheduleBlock]:
    return (
        db.query(DoctorScheduleBlock)
        .filter(DoctorScheduleBlock.doctor_pk == doctor.id)
        .order_by(DoctorScheduleBlock.weekday, DoctorScheduleBlock.start_time)
        .all()
    )


def _to_out(db: Session, doctor: Doctor) -> DoctorOut:
    return DoctorOut(
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
        specialization=doctor.specialization,
        department=doctor.department,
        slot_minutes=doctor.slot_minutes,
        is_active=doctor.is_active,
        schedule=[
            ScheduleBlock(weekday=b.weekday, start_time=b.start_time, end_time=b.end_time)
            for b in _schedule_blocks(db, doctor)
        ],
    )


def _validate_no_overlap(blocks: list[ScheduleBlock]) -> None:
    by_day: dict[int, list[ScheduleBlock]] = {}
    for block in blocks:
        by_day.setdefault(block.weekday, []).append(block)
    for day_blocks in by_day.values():
        day_blocks.sort(key=lambda b: b.start_time)
        for earlier, later in zip(day_blocks, day_blocks[1:]):
            if later.start_time < earlier.end_time:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Schedule blocks overlap on weekday {later.weekday}.",
                )


def _replace_schedule(db: Session, doctor: Doctor, blocks: list[ScheduleBlock]) -> None:
    _validate_no_overlap(blocks)
    db.query(DoctorScheduleBlock).filter(DoctorScheduleBlock.doctor_pk == doctor.id).delete()
    for block in blocks:
        db.add(
            DoctorScheduleBlock(
                doctor_pk=doctor.id, weekday=block.weekday, start_time=block.start_time, end_time=block.end_time
            )
        )


def _audit(db: Session, user: User, event_type: str, detail: str) -> None:
    db.add(AuditLogEntry(event_type=event_type, username=user.username, detail=detail))


# --- Slot calculation (used by US-08 booking) ------------------------------------------------


def schedule_slots(db: Session, doctor: Doctor, day: date) -> list[datetime]:
    """Every slot start the doctor's weekly schedule offers on `day`, booked or not."""
    step = timedelta(minutes=doctor.slot_minutes)
    slots: list[datetime] = []
    for block in _schedule_blocks(db, doctor):
        if block.weekday != day.weekday():
            continue
        current = datetime.combine(day, block.start_time)
        end = datetime.combine(day, block.end_time)
        while current + step <= end:
            slots.append(current)
            current += step
    return slots


def available_slots(db: Session, doctor: Doctor, day: date, now: datetime | None = None) -> list[datetime]:
    """Schedule slots that are in the future and not already booked.

    Computed live from the current schedule and appointments, so a schedule change or a new
    booking is reflected in the very next query (US-07 / AC-HMS-F-005).
    """
    if not doctor.is_active:
        return []
    now = now or utcnow()
    taken = set(booked_slots(db, doctor.doctor_id, day))
    return [s for s in schedule_slots(db, doctor, day) if s > now and s not in taken]


def is_schedule_slot(db: Session, doctor: Doctor, slot_start: datetime) -> bool:
    slot_start = to_utc_naive(slot_start)
    return slot_start in schedule_slots(db, doctor, slot_start.date())


# --- HTTP endpoints --------------------------------------------------------------------------


@router.post(
    "", response_model=DoctorOut, status_code=status.HTTP_201_CREATED, summary="Create a doctor profile"
)
def create_doctor(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(*DOCTOR_ADMIN_ROLES)),
) -> DoctorOut:
    for _ in range(MAX_DOCTOR_ID_GENERATION_ATTEMPTS):
        doctor = Doctor(
            doctor_id=generate_doctor_id(db),
            full_name=payload.full_name.strip(),
            specialization=payload.specialization.strip(),
            department=payload.department.strip(),
            slot_minutes=payload.slot_minutes,
        )
        db.add(doctor)
        try:
            db.flush()
        except IntegrityError:
            # Another concurrent creation took this doctor_id first; retry with a new one.
            db.rollback()
            continue
        break
    else:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Could not create doctor: ID generation is under heavy contention. Try again.",
        )

    _replace_schedule(db, doctor, payload.schedule)
    _audit(db, user, "DOCTOR_CREATED", f"Created doctor {doctor.doctor_id}")
    db.commit()
    return _to_out(db, doctor)


@router.get("", response_model=list[DoctorOut], summary="List doctors")
def list_doctors(
    department: str | None = Query(default=None, max_length=100),
    specialization: str | None = Query(default=None, max_length=100),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[DoctorOut]:
    query = db.query(Doctor)
    if department:
        # Exact (case-insensitive) match: this is a filter, not a search, and ilike() without
        # wrapping the term in %...% would let a caller pass their own % or _ wildcard.
        query = query.filter(func.lower(Doctor.department) == department.strip().lower())
    if specialization:
        query = query.filter(func.lower(Doctor.specialization) == specialization.strip().lower())
    if not include_inactive:
        query = query.filter(Doctor.is_active.is_(True))
    return [_to_out(db, d) for d in query.order_by(Doctor.doctor_id).all()]


@router.get("/{doctor_id}", response_model=DoctorOut, summary="Get a doctor")
def get_doctor(
    doctor_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> DoctorOut:
    return _to_out(db, get_doctor_or_404(db, doctor_id))


@router.patch("/{doctor_id}", response_model=DoctorOut, summary="Update a doctor")
def update_doctor(
    doctor_id: str,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(*DOCTOR_ADMIN_ROLES)),
) -> DoctorOut:
    doctor = get_doctor_or_404(db, doctor_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(doctor, field, value.strip() if isinstance(value, str) else value)
    _audit(db, user, "DOCTOR_UPDATED", f"Updated doctor {doctor.doctor_id}: {sorted(changes)}")
    db.commit()
    return _to_out(db, doctor)


@router.put("/{doctor_id}/schedule", response_model=DoctorOut, summary="Replace a doctor's schedule")
def replace_schedule(
    doctor_id: str,
    blocks: list[ScheduleBlock],
    db: Session = Depends(get_db),
    user: User = Depends(require_role(*DOCTOR_ADMIN_ROLES)),
) -> DoctorOut:
    doctor = get_doctor_or_404(db, doctor_id)
    _replace_schedule(db, doctor, blocks)
    _audit(db, user, "DOCTOR_SCHEDULE_UPDATED", f"Replaced schedule for {doctor.doctor_id} ({len(blocks)} blocks)")
    db.commit()
    return _to_out(db, doctor)


@router.get(
    "/{doctor_id}/available-slots", response_model=AvailableSlots, summary="Get a doctor's available slots"
)
def get_available_slots(
    doctor_id: str,
    day: date,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AvailableSlots:
    doctor = get_doctor_or_404(db, doctor_id)
    return AvailableSlots(doctor_id=doctor.doctor_id, day=day, available=available_slots(db, doctor, day))
