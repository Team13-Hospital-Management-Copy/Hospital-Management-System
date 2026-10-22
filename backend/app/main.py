import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .appointments import router as appointments_router
from .auth import router as auth_router
from .database import Base, SessionLocal, engine
from .notifications import dispatch_due_notifications, get_gateway
from .notifications import router as notifications_router

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


app = FastAPI(title="Hospital Management System API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(appointments_router)
app.include_router(notifications_router)
