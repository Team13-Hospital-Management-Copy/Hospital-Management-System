from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    Appointment,
    AuditLogEntry,
    BILL_STATUS_OPEN,
    BILL_STATUS_PAID,
    Bill,
    BillLineItem,
    PAYMENT_METHODS,
    Patient,
    Payment,
)
from .rbac import require_role
from .roles import RECEPTIONIST
from .schemas import (
    BILL_LINE_CATEGORIES,
    BillCreate,
    BillLineItemCreate,
    BillOut,
    DiscountApply,
    PaymentCreate,
)

# US-17 / HMS-F-014/015/016: billing is handled by reception ("Receptionist: ... handle
# billing-related operations" per the SRS's role descriptions). There's no separate
# insurance/discount-scheme catalog in scope - a discount is applied directly on the bill by
# whoever has this role, rather than picked from an admin-managed list of schemes.
BILLING_ROLES = (RECEPTIONIST,)

router = APIRouter(prefix="/billing", tags=["Billing"])

ZERO = Decimal("0.00")


def _bill_out(db: Session, bill: Bill) -> BillOut:
    items = (
        db.query(BillLineItem)
        .filter(BillLineItem.bill_id == bill.id)
        .order_by(BillLineItem.id)
        .all()
    )
    payments = db.query(Payment).filter(Payment.bill_id == bill.id).order_by(Payment.id).all()

    subtotal = sum((item.amount for item in items), ZERO)
    if bill.discount_percent is not None:
        discount = (subtotal * bill.discount_percent / Decimal("100")).quantize(ZERO)
    elif bill.discount_amount is not None:
        discount = bill.discount_amount
    else:
        discount = ZERO
    total = max(subtotal - discount, ZERO)
    amount_paid = sum((p.amount for p in payments), ZERO)

    return BillOut(
        id=bill.id,
        patient_uhid=bill.patient_uhid,
        appointment_id=bill.appointment_id,
        status=bill.status,
        line_items=items,
        subtotal=subtotal,
        discount_percent=bill.discount_percent,
        discount_amount=bill.discount_amount,
        discount_reason=bill.discount_reason,
        total=total,
        amount_paid=amount_paid,
        balance_due=max(total - amount_paid, ZERO),
        payments=payments,
        created_at=bill.created_at,
    )


def _get_open_bill(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found.")
    if bill.status != BILL_STATUS_OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "This bill is already finalized.")
    return bill


@router.post("/bills", response_model=BillOut, status_code=status.HTTP_201_CREATED, summary="Open a bill")
def create_bill(
    payload: BillCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    patient = db.query(Patient).filter(Patient.uhid == payload.patient_uhid).one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")

    if payload.appointment_id is not None and db.get(Appointment, payload.appointment_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found.")

    bill = Bill(patient_uhid=patient.uhid, appointment_id=payload.appointment_id)
    db.add(bill)
    db.flush()
    db.add(
        AuditLogEntry(
            event_type="BILL_OPENED",
            username=user.username,
            detail=f"bill_id={bill.id}, patient_uhid={patient.uhid}",
        )
    )
    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


@router.post(
    "/bills/{bill_id}/items",
    response_model=BillOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a line item to a bill",
)
def add_line_item(
    bill_id: int,
    payload: BillLineItemCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    bill = _get_open_bill(db, bill_id)

    if payload.category not in BILL_LINE_CATEGORIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"category must be one of {BILL_LINE_CATEGORIES}.",
        )

    db.add(
        BillLineItem(
            bill_id=bill.id,
            category=payload.category,
            description=payload.description.strip(),
            amount=payload.amount,
        )
    )
    db.add(
        AuditLogEntry(
            event_type="BILL_ITEM_ADDED",
            username=user.username,
            detail=f"bill_id={bill.id}, category={payload.category}, amount={payload.amount}",
        )
    )
    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


@router.post(
    "/bills/{bill_id}/discount",
    response_model=BillOut,
    summary="Apply a discount or insurance adjustment",
)
def apply_discount(
    bill_id: int,
    payload: DiscountApply,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    bill = _get_open_bill(db, bill_id)
    current = _bill_out(db, bill)

    if payload.discount_amount is not None and payload.discount_amount > current.subtotal:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Discount cannot exceed the bill subtotal."
        )

    bill.discount_percent = payload.discount_percent
    bill.discount_amount = payload.discount_amount
    bill.discount_reason = payload.reason.strip()

    db.add(
        AuditLogEntry(
            event_type="BILL_DISCOUNT_APPLIED",
            username=user.username,
            detail=(
                f"bill_id={bill.id}, percent={payload.discount_percent}, "
                f"amount={payload.discount_amount}, reason={payload.reason!r}"
            ),
        )
    )
    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


@router.post(
    "/bills/{bill_id}/payments",
    response_model=BillOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment and issue a receipt",
)
def record_payment(
    bill_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    bill = _get_open_bill(db, bill_id)

    if payload.method not in PAYMENT_METHODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"method must be one of {PAYMENT_METHODS}."
        )

    # AC-HMS-F-015: a receipt is generated immediately after the payment is recorded. Card/UPI
    # are recorded the same way cash is - no real payment gateway is wired in (out of scope,
    # same reasoning as US-11's mocked SMS/e-mail gateway).
    payment = Payment(bill_id=bill.id, amount=payload.amount, method=payload.method, receipt_number="")
    db.add(payment)
    db.flush()
    payment.receipt_number = f"RCPT-{payment.id:08d}"

    db.add(
        AuditLogEntry(
            event_type="PAYMENT_RECORDED",
            username=user.username,
            detail=(
                f"bill_id={bill.id}, payment_id={payment.id}, amount={payload.amount}, "
                f"method={payload.method}, receipt={payment.receipt_number}"
            ),
        )
    )
    db.flush()

    totals = _bill_out(db, bill)
    if totals.amount_paid >= totals.total:
        bill.status = BILL_STATUS_PAID

    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


@router.get("/bills/{bill_id}", response_model=BillOut, summary="View a bill")
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role(*BILLING_ROLES)),
):
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found.")
    return _bill_out(db, bill)
