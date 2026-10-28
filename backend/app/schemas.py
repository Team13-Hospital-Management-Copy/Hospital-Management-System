
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    token: str | None = None


class LogoutResponse(BaseModel):
    status: str
    message: str


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    age: int = Field(ge=0, le=130)
    gender: str = Field(min_length=1, max_length=20)
    phone: str = Field(min_length=7, max_length=20)
    address: str = Field(default="", max_length=300)


class PatientResponse(BaseModel):
    id: int
    uhid: str
    full_name: str
    age: int
    gender: str
    phone: str
    address: str


class AppointmentCreate(BaseModel):
    patient_uhid: str
    doctor_id: str
    slot_start: datetime


class AppointmentReschedule(BaseModel):
    new_slot_start: datetime


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_uhid: str
    doctor_id: str
    slot_start: datetime
    status: str
    rescheduled_count: int


# --- Doctor management (US-07) -----------------------------------------------


class ScheduleBlock(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _start_before_end(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class DoctorCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    specialization: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    slot_minutes: int = Field(default=15, ge=5, le=120)
    schedule: list[ScheduleBlock] = Field(default_factory=list)


class DoctorUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    specialization: str | None = Field(default=None, min_length=2, max_length=100)
    department: str | None = Field(default=None, min_length=2, max_length=100)
    slot_minutes: int | None = Field(default=None, ge=5, le=120)
    is_active: bool | None = None


class DoctorOut(BaseModel):
    doctor_id: str
    full_name: str
    specialization: str
    department: str
    slot_minutes: int
    is_active: bool
    schedule: list[ScheduleBlock]


class AvailableSlots(BaseModel):
    doctor_id: str
    day: date
    available: list[datetime]


# --- OPD booking (US-08) ------------------------------------------------------


class OpdBookingRequest(BaseModel):
    patient_uhid: str = Field(min_length=1, max_length=20)
    doctor_id: str = Field(min_length=1, max_length=20)
    department: str | None = Field(default=None, max_length=100)
    slot_start: datetime


# --- Clinical consultation schemas (US-12) -----------------------------------


class ConsultationCreate(BaseModel):
    appointment_id: int = Field(gt=0)
    diagnosis: str = Field(min_length=1, max_length=200)
    blood_pressure: str | None = Field(default=None, max_length=20)
    temperature: str | None = Field(default=None, max_length=20)
    pulse: int | None = Field(default=None, ge=0, le=300)
    spo2: int | None = Field(default=None, ge=0, le=100)
    clinical_notes: str = Field(default="", max_length=2000)


class ConsultationOut(BaseModel):
    id: int
    appointment_id: int
    patient_uhid: str
    diagnosis: str
    blood_pressure: str | None
    temperature: str | None
    pulse: int | None
    spo2: int | None
    clinical_notes: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Lab/radiology test orders (US-14) -----------------------------------------


class LabTestOrderCreate(BaseModel):
    appointment_id: int = Field(gt=0)
    test_name: str = Field(min_length=1, max_length=150)


class LabTestResultUpdate(BaseModel):
    result: str = Field(min_length=1, max_length=2000)


class LabTestOrderOut(BaseModel):
    id: int
    appointment_id: int
    patient_uhid: str
    test_name: str
    status: str
    ordered_by: str
    result: str | None
    ordered_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
