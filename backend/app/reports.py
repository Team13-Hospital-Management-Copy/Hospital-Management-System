import csv
import io
from datetime import date as date_type
from datetime import datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from fpdf import FPDF
from sqlalchemy.orm import Session

from .database import get_db
from .models import APPOINTMENT_STATUS_BOOKED, Admission, Appointment, Bed, Payment
from .rbac import require_role
from .roles import ADMINISTRATOR, SYSTEM_ADMINISTRATOR
from .schemas import ReportSummary

# US-20 / HMS-F-020: "Admin / Management" stakeholder per the SRS.
REPORT_ROLES = (ADMINISTRATOR, SYSTEM_ADMINISTRATOR)

router = APIRouter(prefix="/admin/reports", tags=["Reports"])


def _range_bounds(start_date: date_type, end_date: date_type) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "end_date must not be before start_date."
        )
    return datetime.combine(start_date, time.min), datetime.combine(end_date, time.max)


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def build_summary(db: Session, start_date: date_type, end_date: date_type) -> ReportSummary:
    range_start, range_end = _range_bounds(start_date, end_date)

    # OPD footfall: appointments actually kept (BOOKED, not cancelled) with a slot in range.
    # Appointment.slot_start is naive UTC, so a direct DB-level filter is safe here (same
    # pattern appointments.booked_slots() already uses).
    opd_footfall = (
        db.query(Appointment)
        .filter(
            Appointment.status == APPOINTMENT_STATUS_BOOKED,
            Appointment.slot_start >= range_start,
            Appointment.slot_start <= range_end,
        )
        .count()
    )

    # Revenue: actual cash collected in the range, from the US-17 Payment ledger - this is
    # the "underlying transaction record" the AC asks the exported total to match.
    payments = (
        db.query(Payment).filter(Payment.paid_at >= range_start, Payment.paid_at <= range_end).all()
    )
    revenue = sum((p.amount for p in payments), Decimal("0.00"))

    # Bed occupancy: bed-days actually occupied in the range, against bed-days available.
    # Admission.admitted_at/discharged_at are DateTime(timezone=True): SQLite drops tzinfo on
    # read-back (the same footgun fixed project-wide for AuthToken/Appointment in US-03), so
    # this is computed in Python after normalising to naive UTC, not filtered in SQL.
    total_beds = db.query(Bed).filter(Bed.is_active.is_(True)).count()
    days_in_range = (end_date - start_date).days + 1
    available_bed_days = total_beds * days_in_range

    occupied_bed_days = 0
    admissions_in_range = 0
    for admission in db.query(Admission).all():
        admitted_at = _naive(admission.admitted_at)
        discharged_at = _naive(admission.discharged_at) if admission.discharged_at else range_end
        overlap_start = max(admitted_at, range_start)
        overlap_end = min(discharged_at, range_end)
        if overlap_end < overlap_start:
            continue
        admissions_in_range += 1
        occupied_bed_days += (overlap_end.date() - overlap_start.date()).days + 1

    bed_occupancy_rate = (occupied_bed_days / available_bed_days) if available_bed_days > 0 else 0.0

    return ReportSummary(
        start_date=start_date,
        end_date=end_date,
        opd_footfall=opd_footfall,
        revenue=revenue,
        admissions_in_range=admissions_in_range,
        occupied_bed_days=occupied_bed_days,
        available_bed_days=available_bed_days,
        bed_occupancy_rate=round(bed_occupancy_rate, 4),
    )


def _rows(summary: ReportSummary) -> list[tuple[str, str]]:
    return [
        ("OPD Footfall", str(summary.opd_footfall)),
        ("Revenue", f"{summary.revenue:.2f}"),
        ("Admissions in range", str(summary.admissions_in_range)),
        ("Occupied bed-days", str(summary.occupied_bed_days)),
        ("Available bed-days", str(summary.available_bed_days)),
        ("Bed occupancy rate", f"{summary.bed_occupancy_rate:.2%}"),
    ]


def _csv_bytes(summary: ReportSummary) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Hospital Management System - Operational Report"])
    writer.writerow(["Period", f"{summary.start_date} to {summary.end_date}"])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    for label, value in _rows(summary):
        writer.writerow([label, value])
    return buffer.getvalue().encode("utf-8")


def _pdf_bytes(summary: ReportSummary) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Hospital Management System - Operational Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Period: {summary.start_date} to {summary.end_date}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(90, 8, "Metric", border=1)
    pdf.cell(60, 8, "Value", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for label, value in _rows(summary):
        pdf.cell(90, 8, label, border=1)
        pdf.cell(60, 8, value, border=1, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


@router.get("/summary", response_model=ReportSummary, summary="Operational report summary")
def get_report_summary(
    start_date: date_type = Query(...),
    end_date: date_type = Query(...),
    db: Session = Depends(get_db),
    _user=Depends(require_role(*REPORT_ROLES)),
) -> ReportSummary:
    return build_summary(db, start_date, end_date)


@router.get("/export", summary="Export the operational report as PDF or CSV")
def export_report(
    start_date: date_type = Query(...),
    end_date: date_type = Query(...),
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    db: Session = Depends(get_db),
    _user=Depends(require_role(*REPORT_ROLES)),
) -> Response:
    summary = build_summary(db, start_date, end_date)
    filename = f"hms-report-{start_date}-to-{end_date}.{format}"

    if format == "pdf":
        content, media_type = _pdf_bytes(summary), "application/pdf"
    else:
        content, media_type = _csv_bytes(summary), "text/csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
