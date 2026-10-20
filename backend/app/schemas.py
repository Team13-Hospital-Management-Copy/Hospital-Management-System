from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str

    
from pydantic import BaseModel, Field


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

