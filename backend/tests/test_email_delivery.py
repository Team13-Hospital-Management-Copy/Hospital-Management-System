from datetime import timedelta
from email.message import EmailMessage

import pytest

from app import notifications
from app.models import Notification, Patient
from app.notifications import SmtpNotificationGateway, utcnow


class FakeSmtp:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.credentials = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def starttls(self, context):
        assert context is not None
        self.started_tls = True

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, message: EmailMessage):
        self.message = message


def test_smtp_gateway_sends_email_using_starttls(monkeypatch):
    FakeSmtp.instances.clear()
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "mailer@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_FROM", "Hospital <mailer@example.com>")

    SmtpNotificationGateway().send("EMAIL", "patient@example.com", "Appointment confirmed")

    smtp = FakeSmtp.instances[0]
    assert (smtp.host, smtp.port, smtp.timeout) == ("smtp.example.com", 587, 15.0)
    assert smtp.started_tls is True
    assert smtp.credentials == ("mailer@example.com", "app-password")
    assert smtp.message["To"] == "patient@example.com"
    assert smtp.message["Subject"] == "Hospital appointment update"
    assert "Appointment confirmed" in smtp.message.get_content()


def test_smtp_gateway_does_not_claim_success_without_configuration(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)

    with pytest.raises(RuntimeError, match="not configured"):
        SmtpNotificationGateway().send("EMAIL", "patient@example.com", "Appointment confirmed")


def test_email_notification_uses_registered_patient_email(
    client, db_session, receptionist_header
):
    patient = Patient(
        uhid="HMS-EMAIL-1",
        full_name="Email Patient",
        age=30,
        gender="F",
        phone="9876543210",
        email="patient@example.com",
    )
    db_session.add(patient)
    db_session.commit()

    response = client.post(
        "/appointments",
        json={
            "patient_uhid": patient.uhid,
            "doctor_id": "DOC-1",
            "slot_start": (utcnow() + timedelta(days=30)).isoformat(),
        },
        headers=receptionist_header,
    )

    assert response.status_code == 201, response.text
    email_notification = (
        db_session.query(Notification)
        .filter(
            Notification.appointment_id == response.json()["id"],
            Notification.channel == "EMAIL",
            Notification.kind == "CONFIRMATION",
        )
        .one()
    )
    assert email_notification.recipient == "patient@example.com"
