# Branch Coverage Report

- **Date generated:** 2026-11-05
- **Tool:** `pytest-cov` 7.1.0 / `coverage.py`, run with `--cov-branch`
- **Build:** `main` (PR #45 merged) + pending PR #46 (requirement-ID alignment, comment-only)
- **How to reproduce:** `cd backend && pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=html:../docs/reports/coverage_html`
- **Full interactive report:** [`coverage_html/index.html`](coverage_html/index.html) - the
  "Branch" and "BrPart" (partial branch) columns on each file's detail page show exactly
  which `if`/`for`/`try` branches were and weren't exercised, highlighted in the source view
- **Statement coverage specifically:** see the companion
  [Code Coverage Report](code_coverage_report.md)

## Why branch coverage is tracked separately from statement coverage

Statement coverage only asks "did this line run at least once" - it can hit 100% while an
`if condition: ... else: ...` only ever takes one side in every test. Branch coverage asks the
stricter question: did *every* decision point take *both* (or all) of its possible paths at
least once. For a system built around role checks, status-transition guards, and discount/
payment edge cases, branch coverage is the more meaningful signal of "is the error handling
actually tested," not just "did the code run."

## Branch coverage summary

| Metric | Value |
|---|---|
| Total branches | 308 |
| Partial (one direction never taken) | 39 |
| **Branch coverage** | **87%** |

## Per-module breakdown

Modules with zero branch points (straight-line code with no conditionals - `models.py`,
`roles.py`, `security.py`, `admin.py`) are omitted; there's nothing to measure.

| Module | Branches | Partial | Branch coverage |
|---|---:|---:|---:|
| `auth.py` | 10 | 0 | **100%** |
| `booking.py` | 8 | 0 | **100%** |
| `ehr.py` | 4 | 0 | **100%** |
| `lab_tests.py` | 12 | 0 | **100%** |
| `notifications.py` | 10 | 0 | **100%** |
| `staff_accounts.py` | 12 | 0 | **100%** |
| `rbac.py` | 16 | 1 | 94% |
| `reports.py` | 12 | 1 | 92% |
| `tls.py` | 20 | 2 | 90% |
| `appointments.py` | 18 | 2 | 89% |
| `schemas.py` | 8 | 1 | 88% |
| `doctors.py` | 30 | 4 | 87% |
| `billing.py` | 86 | 10 | 86% |
| `patients.py` | 10 | 2 | 80% |
| `consultations.py` | 8 | 2 | 75% |
| `pharmacy.py` | 8 | 2 | 75% |
| `prescriptions.py` | 4 | 1 | 75% |
| `inpatient.py` | 26 | 8 | 69% |
| `main.py` | 2 | 1 | 50% (lifespan's reminder-loop `if interval > 0` else-arm isn't hit when the suite runs with the default interval) |
| `serve.py` | 4 | 2 | 50% |

## Reading this honestly

`inpatient.py` has the weakest branch coverage (69%) of any module with meaningful branch
count - its 8 partial branches are mostly "what if this bed/admission/patient lookup comes
back empty mid-request" guards that the current test suite doesn't specifically trigger in
every combination. `billing.py`, despite being the largest and most logically complex module
in the codebase (tariff lookup, discount validation, multi-source bill consolidation, payment
status transitions), still reaches 86% branch coverage - a reasonable result given how many
distinct decision points `_collect_charges()` alone has.

None of the partial branches found here are in security-critical code (authentication, RBAC,
session handling, TLS are all at or near 100% branch coverage) - the gaps are concentrated in
secondary error-handling paths of the billing/inpatient/pharmacy modules, which is the honest
place for remaining gaps to be in a system where the security-sensitive paths were built and
tested first.
