
from fastapi import FastAPI

from .auth import router as auth_router
from .database import Base, engine
from .patients import router as patients_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hospital Management System API")
app.include_router(auth_router)
app.include_router(patients_router)
