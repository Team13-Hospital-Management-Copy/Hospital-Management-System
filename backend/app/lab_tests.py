from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    APPOINTMENT_STATUS_BOOKED,
    Appointment,
    AuditLogEntry,
    LAB_TEST_STATUS_COMPLETED,
    LabTestOrder,
)
from .rbac import require_role
from .roles import DOCTOR
from .schemas import LabTestOrderCreate, LabTestOrderOut, LabTestResultUpdate

# US-14: ordering a test and recording its result are both clinical actions tied to a visit,
# same as consultations (US-12) and prescriptions (US-13); there's no separate lab-technician
# role in the SRS's role list, so DOCTOR covers both steps here.
router = APIRouter(prefix="/lab-tests", tags=["Lab Tests"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post(
    "",
    response_model=LabTestOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Order a lab test",
)
def order_lab_test(
    payload: LabTestOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(DOCTOR)),
):
    appointment = db.get(Appointment, payload.appointment_id)

    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found.")

    if appointment.status != APPOINTMENT_STATUS_BOOKED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Lab tests can only be ordered for booked appointments.",
        )

    test_name = payload.test_name.strip()
    if not test_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Test name cannot be blank.")

    order = LabTestOrder(
        appointment_id=appointment.id,
        patient_uhid=appointment.patient_uhid,
        test_name=test_name,
        ordered_by=current_user.username,
    )
    db.add(order)
    db.flush()

    db.add(
        AuditLogEntry(
            event_type="LAB_TEST_ORDERED",
            username=current_user.username,
            detail=(
                f"lab_test_id={order.id}, appointment_id={appointment.id}, "
                f"patient_uhid={appointment.patient_uhid}, test_name={test_name}"
            ),
        )
    )
    db.commit()
    db.refresh(order)
    return order


@router.post(
    "/{lab_test_id}/result",
    response_model=LabTestOrderOut,
    summary="Record a lab test result",
)
def record_result(
    lab_test_id: int,
    payload: LabTestResultUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(DOCTOR)),
):
    order = db.get(LabTestOrder, lab_test_id)

    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab test order not found.")

    if order.status == LAB_TEST_STATUS_COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This lab test already has a recorded result."
        )

    result = payload.result.strip()
    if not result:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Result cannot be blank.")

    order.result = result
    order.status = LAB_TEST_STATUS_COMPLETED
    order.completed_at = _utcnow()

    db.add(
        AuditLogEntry(
            event_type="LAB_TEST_RESULT_RECORDED",
            username=current_user.username,
            detail=(
                f"lab_test_id={order.id}, patient_uhid={order.patient_uhid}, "
                f"test_name={order.test_name}"
            ),
        )
    )
    db.commit()
    db.refresh(order)
    return order


@router.get(
    "/{patient_uhid}",
    response_model=list[LabTestOrderOut],
    summary="List a patient's lab tests",
)
def list_patient_lab_tests(
    patient_uhid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(DOCTOR)),
):
    orders = (
        db.query(LabTestOrder)
        .filter(LabTestOrder.patient_uhid == patient_uhid)
        .order_by(LabTestOrder.ordered_at.desc())
        .all()
    )

    db.add(
        AuditLogEntry(
            event_type="LAB_TESTS_VIEWED",
            username=current_user.username,
            detail=f"patient_uhid={patient_uhid}, count={len(orders)}",
        )
    )
    db.commit()
    return orders
