# Hospital Management System (HMS)

## About the Project

The Hospital Management System (HMS) is a centralized software application designed to simplify and manage hospital operations. It helps organize patient information, doctor details, appointments, medical records, prescriptions, billing, and reports in one system.

The project aims to improve the efficiency, accuracy, security, and accessibility of hospital information management.

## Objectives

- Centralize hospital-related information.
- Simplify patient registration and profile management.
- Manage doctor details and availability.
- Schedule, cancel, and reschedule appointments.
- Maintain patient medical records and electronic prescriptions.
- Manage billing and payment records.
- Provide secure, role-based access to information.

## Features

- **User Authentication:** Login, logout, and session management.
- **Patient Management:** Register patients and manage their profiles.
- **Doctor Management:** Maintain doctor profiles, specializations, departments, and availability.
- **Appointment Management:** Schedule appointments, check availability, and prevent double booking.
- **Medical Records:** Record and retrieve diagnosis, treatment details, and consultation notes.
- **Prescription Management:** Create electronic prescriptions and maintain medicine dispensing records.
- **Billing and Payments:** Generate bills and record payment status.
- **Reports and Notifications:** Generate hospital reports and support appointment confirmations and reminders.
- **Role-Based Access Control:** Restrict access according to user roles.
- **Security:** Protect sensitive patient information and maintain audit logs.

## User Roles

The system is designed to support the following roles:

- **Patient:** Manage permitted profile information, appointments, and access to authorized records.
- **Doctor:** View appointments, access authorized patient records, record consultations, and create prescriptions.
- **Receptionist:** Register patients, manage appointments, and handle billing-related operations.
- **Pharmacist:** View authorized prescriptions and maintain medicine dispensing records.
- **Administrator:** Manage users, doctors, departments, and reports.
- **System Administrator:** Handle system maintenance, security, backups, and monitoring.

## System Architecture

The system follows a proposed layered and modular centralized architecture consisting of:

1. Presentation Layer
2. Application / Service Layer
3. Security Layer
4. Domain / Business Modules
5. Data Access Layer
6. Integration Layer

These layers separate user interaction, business logic, security, data management, and external service interfaces.

## Security

Security is an important part of the system. The design includes:

- Authentication and role-based authorization.
- Secure password hashing.
- HTTPS communication using TLS 1.2 or higher.
- Session management and automatic timeout.
- Audit logging for sensitive operations.
- Protection of patient and medical records.

## Testing

The project testing plan covers:

- Unit Testing
- Integration Testing
- System Testing
- User Acceptance Testing (UAT)
- Functional Testing
- Security Testing
- Performance Testing
- Usability Testing
- Compatibility Testing
- Regression Testing

## Installation and Setup

The backend is a FastAPI app and the frontend is a Next.js app - see each one's README for
setup:

- [`backend/README.md`](backend/README.md) - API setup, running, and database configuration
  (SQLite for local dev, Postgres/MySQL for anything beyond that).
- [`frontend/README.md`](frontend/README.md) - demo UI covering Sprint 1 (staff login, doctor
  setup, patient registration, OPD appointment booking).

Or run both together with Docker:

```bash
docker-compose up --build
```

This builds and starts both services (backend on :8000, frontend on :3000), with the SQLite
database persisted in a named volume across restarts.

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push/PR to `main`:

- **CI** - backend tests (`pytest`) and frontend checks (lint, type-check, build).
- **CD** - once code lands on `main` *and* CI is green, builds and publishes versioned Docker
  images for both services to GitHub Container Registry
  (`ghcr.io/team13-hospital-management-copy/hms-backend` and `hms-frontend`, tagged `latest` and
  by commit SHA). This is continuous *delivery* (an image is always ready to run) rather than
  continuous *deployment* - nothing automatically runs these images anywhere, since the project
  has no live hosting target.

## Project Team

**Team 13 — Section K**

- Vanishree
- Nisarga
- Shloka
- Parnika

## Project Status

Academic software engineering project. Features and implementation details will be updated as development progresses.


## Patient Registration and UHID Retrieval (US-05)

### Register a Patient

**Endpoint:** `POST /patients/`

Registers a new patient and generates a Unique Hospital Identification (UHID).

Example request:

```json
{
  "full_name": "Test Patient",
  "age": 30,
  "gender": "Female",
  "phone": "9876543210",
  "address": "Test Address"
}
```

A successful registration returns `201 Created` with the patient's details and generated UHID.

### Retrieve a Patient

**Endpoint:** `GET /patients/{uhid}`

Retrieves a patient record using its UHID.

Example: `GET /patients/HMS-000001`

- `200 OK` — Patient found.
- `404 Not Found` — Patient does not exist.

### Validation

- `age` must be between 0 and 130.
- `full_name` must contain between 2 and 150 characters.
- `gender` must contain between 1 and 20 characters.
- `phone` must contain between 7 and 20 characters.
- `address` is optional and can contain up to 300 characters.
