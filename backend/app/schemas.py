from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    token: str | None = None


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
