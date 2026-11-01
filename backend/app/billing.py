import math
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    Admission,
    Appointment,
    AuditLogEntry,
    BILL_STATUS_OPEN,
    BILL_STATUS_PAID,
    BILL_STATUS_PARTIALLY_PAID,
    Bed,
    Bill,
    BillLineItem,
    Consultation,
    DiscountScheme,
    Doctor,
    LabTestOrder,
    MedicineBatch,
    PAYMENT_METHODS,
    Patient,
    Payment,
    PharmacyDispenseRecord,
    ServiceTariff,
)
from .rbac import require_role
from .roles import ADMINISTRATOR, RECEPTIONIST, SYSTEM_ADMINISTRATOR
from .schemas import (
    BILL_LINE_CATEGORIES,
    BillCreate,
    BillLineItemCreate,
    BillOut,
    DiscountApply,
    DiscountSchemeCreate,
    DiscountSchemeOut,
    PaymentCreate,
    TariffOut,
    TariffUpsert,
)

# US-17 / HMS-F-018 (bill generation) / HMS-F-019 (payment recording): the SRS gives billing to
# "authorized receptionists or billing staff"; there is no separate billing-staff role, so
# RECEPTIONIST covers it. Prices and discount schemes are configuration, maintained by admins.
BILLING_ROLES = (RECEPTIONIST,)
CONFIG_ROLES = (ADMINISTRATOR, SYSTEM_ADMINISTRATOR)

router = APIRouter(prefix="/billing", tags=["Billing"])

ZERO = Decimal("0.00")
DEFAULT_TARIFF = "*"

# Consolidation source types (BillLineItem.source_type).
SOURCE_CONSULTATION = "CONSULTATION"
SOURCE_LAB_TEST = "LAB_TEST"
SOURCE_DISPENSE = "DISPENSE"
SOURCE_ADMISSION = "ADMISSION"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


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
        admission_id=bill.admission_id,
        status=bill.status,
        line_items=items,
        subtotal=subtotal,
        discount_percent=bill.discount_percent,
        discount_amount=bill.discount_amount,
        discount_reason=bill.discount_reason,
        discount_scheme_id=bill.discount_scheme_id,
        total=total,
        amount_paid=amount_paid,
        balance_due=max(total - amount_paid, ZERO),
        payments=payments,
        created_at=bill.created_at,
    )


def _refresh_status(db: Session, bill: Bill) -> None:
    """HMS-F-019: keep the bill's payment status in step with what has been paid."""
    db.flush()
    totals = _bill_out(db, bill)
    if totals.subtotal > ZERO and totals.amount_paid >= totals.total:
        bill.status = BILL_STATUS_PAID  # includes a bill discounted to zero
        bill.finalized_at = bill.finalized_at or _utcnow()
    elif totals.amount_paid > ZERO:
        bill.status = BILL_STATUS_PARTIALLY_PAID
    else:
        bill.status = BILL_STATUS_OPEN


def _get_open_bill(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found.")
    if bill.status == BILL_STATUS_PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "This bill is already finalized.")
    return bill


def _audit(db: Session, user, event_type: str, detail: str) -> None:
    # HMS-SR-004: billing changes are written to the audit log.
    db.add(AuditLogEntry(event_type=event_type, username=user.username, detail=detail))


# --- Price list and discount schemes (configuration) -----------------------------------------


@router.put("/tariffs", response_model=TariffOut, summary="Set a price in the tariff")
def upsert_tariff(
    payload: TariffUpsert,
    db: Session = Depends(get_db),
    user=Depends(require_role(*CONFIG_ROLES)),
):
    if payload.category not in BILL_LINE_CATEGORIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"category must be one of {BILL_LINE_CATEGORIES}."
        )
    item_name = payload.item_name.strip()
    tariff = (
        db.query(ServiceTariff)
        .filter(ServiceTariff.category == payload.category, func.lower(ServiceTariff.item_name) == item_name.lower())
        .one_or_none()
    )
    if tariff is None:
        tariff = ServiceTariff(category=payload.category, item_name=item_name, unit_price=payload.unit_price)
        db.add(tariff)
    else:
        tariff.unit_price = payload.unit_price
        tariff.updated_at = _utcnow()
    _audit(db, user, "TARIFF_SET", f"{payload.category}/{item_name}={payload.unit_price}")
    db.commit()
    db.refresh(tariff)
    return tariff


@router.get("/tariffs", response_model=list[TariffOut], summary="List the tariff")
def list_tariffs(
    db: Session = Depends(get_db),
    _user=Depends(require_role(*BILLING_ROLES, *CONFIG_ROLES)),
):
    return db.query(ServiceTariff).order_by(ServiceTariff.category, ServiceTariff.item_name).all()


@router.post(
    "/discount-schemes",
    response_model=DiscountSchemeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an insurance/discount scheme",
)
def create_discount_scheme(
    payload: DiscountSchemeCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*CONFIG_ROLES)),
):
    name = payload.name.strip()
    if db.query(DiscountScheme).filter(func.lower(DiscountScheme.name) == name.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A scheme with this name already exists.")
    scheme = DiscountScheme(
        name=name, discount_percent=payload.discount_percent, discount_amount=payload.discount_amount
    )
    db.add(scheme)
    db.flush()
    _audit(
        db, user, "DISCOUNT_SCHEME_CREATED",
        f"scheme_id={scheme.id}, name={name!r}, percent={payload.discount_percent}, amount={payload.discount_amount}",
    )
    db.commit()
    db.refresh(scheme)
    return scheme


@router.get("/discount-schemes", response_model=list[DiscountSchemeOut], summary="List discount schemes")
def list_discount_schemes(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _user=Depends(require_role(*BILLING_ROLES, *CONFIG_ROLES)),
):
    query = db.query(DiscountScheme)
    if not include_inactive:
        query = query.filter(DiscountScheme.is_active.is_(True))
    return query.order_by(DiscountScheme.name).all()


@router.post(
    "/discount-schemes/{scheme_id}/deactivate",
    response_model=DiscountSchemeOut,
    summary="Stop offering a discount scheme",
)
def deactivate_discount_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(*CONFIG_ROLES)),
):
    scheme = db.get(DiscountScheme, scheme_id)
    if scheme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount scheme not found.")
    scheme.is_active = False
    _audit(db, user, "DISCOUNT_SCHEME_DEACTIVATED", f"scheme_id={scheme.id}")
    db.commit()
    db.refresh(scheme)
    return scheme


# --- Bills -----------------------------------------------------------------------------------


@router.post("/bills", response_model=BillOut, status_code=status.HTTP_201_CREATED, summary="Open a bill")
def create_bill(
    payload: BillCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    patient = db.query(Patient).filter(Patient.uhid == payload.patient_uhid).one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.")

    if payload.appointment_id is not None:
        appointment = db.get(Appointment, payload.appointment_id)
        if appointment is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found.")
        if appointment.patient_uhid != patient.uhid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Appointment belongs to a different patient.")

    if payload.admission_id is not None:
        admission = db.get(Admission, payload.admission_id)
        if admission is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Admission not found.")
        if admission.patient_uhid != patient.uhid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Admission belongs to a different patient.")

    bill = Bill(patient_uhid=patient.uhid, appointment_id=payload.appointment_id, admission_id=payload.admission_id)
    db.add(bill)
    db.flush()
    _audit(db, user, "BILL_OPENED", f"bill_id={bill.id}, patient_uhid={patient.uhid}")
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
            quantity=1,
            unit_price=payload.amount,
            amount=payload.amount,
        )
    )
    _audit(db, user, "BILL_ITEM_ADDED", f"bill_id={bill.id}, category={payload.category}, amount={payload.amount}")
    _refresh_status(db, bill)
    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


class _PriceList:
    def __init__(self, db: Session) -> None:
        self._prices = {
            (t.category, t.item_name.strip().lower()): t.unit_price for t in db.query(ServiceTariff).all()
        }
        self.missing: list[str] = []

    def price(self, category: str, item_name: str, label: str) -> Decimal | None:
        found = self._prices.get((category, item_name.strip().lower()))
        if found is None:
            found = self._prices.get((category, DEFAULT_TARIFF))
        if found is None:
            self.missing.append(f"{category}: {label}")
        return found


def _already_billed(db: Session, source_type: str, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    rows = (
        db.query(BillLineItem.source_id)
        .filter(BillLineItem.source_type == source_type, BillLineItem.source_id.in_(ids))
        .all()
    )
    return {r.source_id for r in rows}


def _collect_charges(db: Session, bill: Bill) -> tuple[list[BillLineItem], list[str]]:
    """Everything chargeable for this bill's visit/admission that is not on any bill yet."""
    prices = _PriceList(db)
    lines: list[BillLineItem] = []

    def add(category, description, source_type, source_id, unit_price, quantity=1):
        if unit_price is not None:
            lines.append(
                BillLineItem(
                    bill_id=bill.id,
                    category=category,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    amount=(unit_price * quantity).quantize(ZERO),
                    source_type=source_type,
                    source_id=source_id,
                )
            )

    if bill.appointment_id is not None:
        appointment = db.get(Appointment, bill.appointment_id)

        consultation = db.query(Consultation).filter(Consultation.appointment_id == appointment.id).one_or_none()
        if consultation and consultation.id not in _already_billed(db, SOURCE_CONSULTATION, [consultation.id]):
            doctor = db.query(Doctor).filter(Doctor.doctor_id == appointment.doctor_id).one_or_none()
            department = doctor.department if doctor else DEFAULT_TARIFF
            label = f"OPD consultation ({department})" if doctor else "OPD consultation"
            add("CONSULTATION", label, SOURCE_CONSULTATION, consultation.id,
                prices.price("CONSULTATION", department, label))

        orders = db.query(LabTestOrder).filter(LabTestOrder.appointment_id == appointment.id).order_by(LabTestOrder.id).all()
        billed = _already_billed(db, SOURCE_LAB_TEST, [o.id for o in orders])
        for order in orders:
            if order.id not in billed:
                add("LAB", f"Lab test: {order.test_name}", SOURCE_LAB_TEST, order.id,
                    prices.price("LAB", order.test_name, order.test_name))

    # Dispense records are not linked to a visit, so every medicine dispensed to the patient that
    # is not yet on a bill is included.
    dispenses = (
        db.query(PharmacyDispenseRecord, MedicineBatch)
        .join(MedicineBatch, MedicineBatch.id == PharmacyDispenseRecord.batch_id)
        .filter(PharmacyDispenseRecord.patient_uhid == bill.patient_uhid)
        .order_by(PharmacyDispenseRecord.id)
        .all()
    )
    billed = _already_billed(db, SOURCE_DISPENSE, [d.id for d, _ in dispenses])
    for record, batch in dispenses:
        if record.id not in billed:
            add("PHARMACY", f"Medicine: {batch.medicine_name} (batch {batch.batch_number})", SOURCE_DISPENSE,
                record.id, prices.price("PHARMACY", batch.medicine_name, batch.medicine_name), record.quantity)

    if bill.admission_id is not None:
        admission = db.get(Admission, bill.admission_id)
        if admission.id not in _already_billed(db, SOURCE_ADMISSION, [admission.id]):
            if admission.discharged_at is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Discharge the patient before billing the admission's bed charges."
                )
            bed = db.get(Bed, admission.bed_id)
            stay = _naive_utc(admission.discharged_at) - _naive_utc(admission.admitted_at)
            days = max(1, math.ceil(stay.total_seconds() / 86400))
            add("ROOM", f"Bed {bed.bed_number}, {bed.ward} ward ({days} day{'s' if days != 1 else ''})",
                SOURCE_ADMISSION, admission.id, prices.price("ROOM", bed.ward, f"{bed.ward} ward"), days)

    return lines, prices.missing


@router.post(
    "/bills/{bill_id}/consolidate",
    response_model=BillOut,
    summary="Add all outstanding charges for the visit/admission",
)
def consolidate_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    """US-17 / HMS-F-018: pull the visit's consultation, lab tests, dispensed medicines and bed
    days onto the bill, priced from the tariff.

    Safe to call again: anything already on a bill is skipped, so a later lab test or medicine is
    added without double-billing the rest. If any item has no price in the tariff, nothing is added
    and the response lists what needs a price.
    """
    bill = _get_open_bill(db, bill_id)
    lines, missing = _collect_charges(db, bill)
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "Some items have no price in the tariff.", "missing_prices": missing},
        )

    for line in lines:
        db.add(line)
    if lines:
        _audit(
            db, user, "BILL_CONSOLIDATED",
            f"bill_id={bill.id}, added={len(lines)}, amount={sum((l.amount for l in lines), ZERO)}",
        )
    _refresh_status(db, bill)
    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


@router.post(
    "/bills/{bill_id}/discount",
    response_model=BillOut,
    summary="Apply a discount or insurance scheme",
)
def apply_discount(
    bill_id: int,
    payload: DiscountApply,
    db: Session = Depends(get_db),
    user=Depends(require_role(*BILLING_ROLES)),
):
    bill = _get_open_bill(db, bill_id)
    current = _bill_out(db, bill)

    if current.amount_paid > ZERO:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The discount can't be changed after a payment has been recorded."
        )

    if payload.scheme_id is not None:
        scheme = db.get(DiscountScheme, payload.scheme_id)
        if scheme is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount scheme not found.")
        if not scheme.is_active:
            raise HTTPException(status.HTTP_409_CONFLICT, "This discount scheme is no longer offered.")
        percent, amount = scheme.discount_percent, scheme.discount_amount
        reason = f"Scheme: {scheme.name}"
    else:
        percent, amount = payload.discount_percent, payload.discount_amount
        reason = payload.reason.strip()

    if amount is not None and amount > current.subtotal:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Discount cannot exceed the bill subtotal."
        )

    bill.discount_percent = percent
    bill.discount_amount = amount
    bill.discount_reason = reason
    bill.discount_scheme_id = payload.scheme_id

    _audit(
        db, user, "BILL_DISCOUNT_APPLIED",
        f"bill_id={bill.id}, scheme_id={payload.scheme_id}, percent={percent}, amount={amount}, reason={reason!r}",
    )
    _refresh_status(db, bill)
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

    balance_due = _bill_out(db, bill).balance_due
    if payload.amount > balance_due:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Payment exceeds the balance due ({balance_due})."
        )

    # A receipt is generated immediately after the payment is recorded. Card/UPI are recorded the
    # same way cash is - no real payment gateway is wired in (out of scope, same reasoning as
    # US-11's mocked SMS/e-mail gateway).
    payment = Payment(bill_id=bill.id, amount=payload.amount, method=payload.method, receipt_number="")
    db.add(payment)
    db.flush()
    payment.receipt_number = f"RCPT-{payment.id:08d}"

    _audit(
        db, user, "PAYMENT_RECORDED",
        f"bill_id={bill.id}, payment_id={payment.id}, amount={payload.amount}, "
        f"method={payload.method}, receipt={payment.receipt_number}",
    )
    # HMS-F-019: a valid payment updates the bill's status (PARTIALLY_PAID or PAID).
    _refresh_status(db, bill)
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
