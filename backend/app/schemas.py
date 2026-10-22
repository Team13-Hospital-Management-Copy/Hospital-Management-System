from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    token: str | None = None


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
