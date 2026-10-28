
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import MedicineBatch, Patient, PharmacyDispenseRecord
from .rbac import require_role
from .roles import PHARMACIST

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy"])


class MedicineBatchCreate(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=150)
    batch_number: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)
    expiry_date: date


class DispenseRequest(BaseModel):
    batch_id: int = Field(gt=0)
    patient_uhid: str = Field(min_length=1, max_length=20)
    quantity: int = Field(gt=0)


def batch_response(batch: MedicineBatch) -> dict:
    return {
        "id": batch.id,
        "medicine_name": batch.medicine_name,
        "batch_number": batch.batch_number,
        "quantity": batch.quantity,
        "low_stock_threshold": batch.low_stock_threshold,
        "expiry_date": batch.expiry_date,
        "low_stock": batch.quantity <= batch.low_stock_threshold,
    }


@router.post("/batches", status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: MedicineBatchCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_role(PHARMACIST)),
):
    batch = MedicineBatch(**payload.model_dump())
    db.add(batch)

    try:
        db.commit()
        db.refresh(batch)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A batch with this medicine name and batch number already exists.",
        )

    return batch_response(batch)


@router.get("/batches")
def list_batches(
    db: Session = Depends(get_db),
    _user=Depends(require_role(PHARMACIST)),
):
    batches = (
        db.query(MedicineBatch)
        .order_by(MedicineBatch.medicine_name, MedicineBatch.expiry_date)
        .all()
    )
    return [batch_response(batch) for batch in batches]


@router.post("/dispense", status_code=status.HTTP_201_CREATED)
def dispense(
    payload: DispenseRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_role(PHARMACIST)),
):
    batch = (
        db.query(MedicineBatch)
        .filter(MedicineBatch.id == payload.batch_id)
        .with_for_update()
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine batch not found",
        )

    if batch.expiry_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot dispense an expired batch",
        )

    if batch.quantity < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient stock",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.uhid == payload.patient_uhid)
        .first()
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    try:
        batch.quantity -= payload.quantity

        record = PharmacyDispenseRecord(
            batch_id=batch.id,
            patient_uhid=patient.uhid,
            quantity=payload.quantity,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        db.refresh(batch)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Medicine dispensed successfully",
        "dispense_id": record.id,
        "batch": batch_response(batch),
        "dispensed_quantity": record.quantity,
    }


@router.get("/low-stock")
def low_stock(
    db: Session = Depends(get_db),
    _user=Depends(require_role(PHARMACIST)),
):
    batches = (
        db.query(MedicineBatch)
        .filter(
            MedicineBatch.quantity <= MedicineBatch.low_stock_threshold
        )
        .order_by(MedicineBatch.quantity)
        .all()
    )
    return [batch_response(batch) for batch in batches]


@router.get("/expiry-alerts")
def expiry_alerts(
    within_days: int = Query(default=30, ge=0, le=365),
    db: Session = Depends(get_db),
    _user=Depends(require_role(PHARMACIST)),
):
    today = date.today()
    end_date = today + timedelta(days=within_days)

    batches = (
        db.query(MedicineBatch)
        .filter(
            MedicineBatch.expiry_date >= today,
            MedicineBatch.expiry_date <= end_date,
            MedicineBatch.quantity > 0,
        )
        .order_by(MedicineBatch.expiry_date)
        .all()
    )

    return [
        {
            **batch_response(batch),
            "days_until_expiry": (batch.expiry_date - today).days,
        }
        for batch in batches
    ]
