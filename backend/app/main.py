from fastapi import FastAPI

from .admin import router as admin_router
from .auth import router as auth_router
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hospital Management System API")
app.include_router(auth_router)
app.include_router(admin_router)
