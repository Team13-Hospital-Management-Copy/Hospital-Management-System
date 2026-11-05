# Code Coverage Report

- **Date generated:** 2026-11-05
- **Tool:** `pytest-cov` 7.1.0 / `coverage.py`
- **Build:** `main` (PR #45 merged) + pending PR #46 (requirement-ID alignment, comment-only)
- **How to reproduce:** `cd backend && pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=html:../docs/reports/coverage_html --cov-report=xml:../docs/reports/coverage.xml`
- **Full interactive report:** [`coverage_html/index.html`](coverage_html/index.html) (open in a
  browser - click any file to see exactly which lines ran)
- **Machine-readable:** [`coverage.xml`](coverage.xml) (Cobertura format, importable into most CI
  dashboards)
- **Branch coverage specifically:** see the companion
  [Branch Coverage Report](branch_coverage_report.md)

## Statement coverage summary

| Metric | Value |
|---|---|
| Statements | 1,914 |
| Missed | 75 |
| **Statement coverage** | **96%** |

These are pure statement numbers, pulled from `coverage.py`'s JSON report
(`percent_statements_covered`) - note this is a different, higher figure than the single
blended "Cover" column `coverage report`'s terminal output shows when run with `--cov-branch`,
which mixes statement *and* branch results into one number. Keeping the two separate (see the
[Branch Coverage Report](branch_coverage_report.md) for that one) is more honest than quoting
the blended figure as if it were either.

## Per-module breakdown

| Module | Statements | Missed | Statement coverage |
|---|---:|---:|---:|
| `__init__.py` | 0 | 0 | **100%** |
| `admin.py` | 11 | 0 | **100%** |
| `auth.py` | 50 | 0 | **100%** |
| `ehr.py` | 23 | 0 | **100%** |
| `lab_tests.py` | 51 | 0 | **100%** |
| `models.py` | 210 | 0 | **100%** |
| `roles.py` | 7 | 0 | **100%** |
| `security.py` | 5 | 0 | **100%** |
| `staff_accounts.py` | 50 | 0 | **100%** |
| `notifications.py` | 93 | 1 | 99% |
| `schemas.py` | 274 | 1 | 99% |
| `reports.py` | 82 | 1 | 98% |
| `appointments.py` | 129 | 2 | 97% |
| `rbac.py` | 62 | 1 | 97% |
| `main.py` | 65 | 2 | 96% |
| `booking.py` | 34 | 2 | 95% |
| `doctors.py` | 114 | 5 | 94% |
| `prescriptions.py` | 28 | 1 | 94% |
| `billing.py` | 249 | 12 | 93% |
| `tls.py` | 55 | 5 | 91% |
| `consultations.py` | 28 | 2 | 89% |
| `patients.py` | 54 | 5 | 89% |
| `pharmacy.py` | 70 | 8 | 87% |
| `inpatient.py` | 130 | 14 | 86% |
| `database.py` | 16 | 4 | 75% |
| `serve.py` | 24 | 9 | 61% |

## Where the gaps are, and why they're not concerning

- **`serve.py` (61%)** - the standalone HTTPS entrypoint (`python -m app.serve`), used only
  when running the app without a reverse proxy terminating TLS. Every test hits the app
  through FastAPI's `TestClient` directly, which never calls this module's `main()`/CLI
  argument handling. Its actual TLS-handshake *logic* is tested directly and thoroughly in
  `test_tls.py` (16 tests) - what's uncovered here is argument parsing and the
  `if __name__ == "__main__"` wiring, not security-relevant code paths.
- **`database.py` (75%)** - the 4 missed lines are the body of `get_db()` itself (lines 25-29:
  open a session, yield it, close it in `finally`). `conftest.py` replaces this function
  entirely via FastAPI's `app.dependency_overrides[get_db] = override_get_db` for every test,
  so the real implementation never runs during the suite - only its own test-only
  replacement does. It does run on every real request outside of tests (any local `uvicorn`
  run exercises it immediately), so this is a test-harness artifact, not a dead code path.
- **`inpatient.py` (86%) / `pharmacy.py` (87%)** - a handful of defensive error branches
  (e.g. a bed or batch that's missing mid-request) not yet given their own dedicated test case.
  Worth closing if there's time before the final demo, but these are edge cases, not core
  paths - the core admit/discharge and batch/dispense flows are covered.
- **`billing.py` (93%, 12 missed of 249)** - the largest module in the codebase; the missed
  lines are scattered single-branch edge cases (e.g. a specific combination of already-billed
  source records) rather than one unexercised feature.
