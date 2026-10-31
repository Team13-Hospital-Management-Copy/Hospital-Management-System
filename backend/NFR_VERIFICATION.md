# US-21: NFR Verification Report

Verification pass against US-21's stated acceptance criteria, run 2026-11-01. This is an
honest account of what was actually checked, what was found and fixed, and - just as
importantly - what *wasn't* verified and why, rather than a claim that every AC was fully
satisfied.

## 0. A reference mismatch found during this pass

US-21's issue body cites `AC-HMS-SR-003` for the audit-logging requirement. In the current
SRS (`Team-13_SRS.pdf`), **`HMS-SR-003` is actually "store user passwords using strong
one-way hashing... never store passwords in plain text"** (already satisfied by US-01's
bcrypt hashing, unrelated to audit logs). The audit-logging requirement is actually
**`HMS-SR-004`**: "maintain audit logs for authentication events, patient record
modifications, billing changes, prescription changes, and administrative actions." The
issue also cites `HMS-NF-006`, which doesn't exist anywhere in the current SRS (only
`HMS-NF-001` through `HMS-NF-005` are defined).

This verification was run against the correct current requirement (`HMS-SR-004`), not the
issue's stale reference - flagging the drift rather than silently working around it, since
it suggests the backlog issue was written against an earlier SRS revision than the one
currently in the repo.

## 1. AC-HMS-SR-004 (cited in the issue as SR-003): audit logging — PASS, one gap found and fixed

**Requirement (as the issue states it):** every create/read/update/delete operation on an
EHR record produces a corresponding audit-log entry.

**Finding:** `GET /patients/{uhid}/ehr` (the longitudinal EHR view, US-15) was not
audit-logged. Every *write* in the EHR chain already was (`CONSULTATION_CREATED`,
`PRESCRIPTION_CREATED`, `LAB_TEST_ORDERED`, `LAB_TEST_RESULT_RECORDED`,
`PRESCRIPTIONS_VIEWED`, `LAB_TESTS_VIEWED`), but this one *read* endpoint wasn't - a real
gap against the issue's explicit "read" requirement.

**Fix:** added an `EHR_VIEWED` audit log entry to `ehr.py`'s `GET /patients/{uhid}/ehr`.

**Verified by:** `tests/test_nfr_verification.py::test_ehr_create_and_read_operations_are_audit_logged`,
which exercises a full create chain (consultation → prescription → lab test order → lab
result) plus the EHR read, and asserts an audit log entry exists for every one of them.

**Scope note:** "EHR record" is scoped to what `ehr.py` itself aggregates - consultations,
prescriptions, lab test orders/results. Patient demographic reads (`GET /patients/{uhid}`)
and doctor/appointment reads are not treated as EHR records here; they're a separate concern
from clinical history.

## 2. AC-HMS-NF-001: performance (P90 ≤ 3s at 200 concurrent users) — PARTIALLY VERIFIED, honestly scaled down

**What the AC asks for:** P90 response time ≤ 3 seconds at 200 *concurrent* users under
production-like load.

**What wasn't possible here, and why:** genuine multi-threaded concurrency against this
project's test database isn't safe to exercise - the test harness's SQLite connection
(`StaticPool`, a single shared connection) throws `sqlite3.InterfaceError: bad parameter or
other API misuse` under real concurrent multi-threaded access; this is a driver-level
limitation, not an application bug. A true 200-concurrent-user load test needs dedicated
load-testing infrastructure (e.g. Locust or k6 against a real multi-connection Postgres
deployment) that this project doesn't have.

**What was actually measured:** P90 latency over 200 *sequential* real HTTP requests
(`httpx` against a live `uvicorn` server, not the in-process test client, so this includes
real TCP/HTTP overhead) to a representative authenticated read endpoint:

| Metric | Value |
|---|---|
| Sample size | 200 requests |
| Min | 2.72 ms |
| P50 | 3.59 ms |
| **P90** | **6.54 ms** |
| P99 | 8.51 ms |
| Max | 27.24 ms |

P90 is **6.54ms**, far under the 3,000ms budget - strong evidence individual transactions
are fast. It is **not** evidence about throughput under 200 simultaneous users, which is a
different property (queueing/contention under load) that this measurement can't speak to.
`tests/test_nfr_verification.py::test_representative_endpoint_response_time_under_budget`
runs the same check (200 sequential requests, P90 ≤ 3s) on every CI run as a regression
guard, with the same caveat documented in its docstring.

## 3. AC-HMS-NF-004: usability (new staff complete tasks after ≤ 2 hours of training) — NOT VERIFIED

This requires an actual human-subjects usability study with real new staff, timed training
and task completion. No such study was run - there's no user panel available for this
project, and fabricating "results" would be worse than stating plainly that this wasn't
done.

**What exists instead, as supporting (not substitute) evidence:**
- The Sprint 1 demo UI's dashboard presents the core workflow as a numbered, color-coded
  1→2→3 sequence (violet/teal/rose per action) rather than an undifferentiated menu.
- Every form validates inline and every API error returns a specific, human-readable message
  (never a bare stack trace or generic "error").
- The backend's own `/docs` (Swagger UI) is fully navigable and testable by a new developer
  without reading source code first.

None of this is a substitute for AC-HMS-NF-004. If this needs to be formally closed out, it
needs a scheduled session with 2-3 people who haven't seen the system before, a stopwatch,
and a short task list (register a patient, book an appointment) - that's a half-day of
coordination this verification pass didn't have.

## 4. HMS-NF-002: reliability (≥ 99.5% monthly availability, ops/monitoring review) — NOT VERIFIED

This requires production monitoring data accumulated over a real month of operation. **There
is no production deployment** - the CD pipeline (added for Sprint 2) publishes Docker images
to GitHub Container Registry, but nothing runs them continuously anywhere, so there's no
uptime to measure.

**Architectural properties that support the target, documented instead of fabricated
monitoring data:**
- The background reminder-dispatch loop (`main.py`'s `_reminder_loop`) catches every
  exception and keeps running rather than crashing the process - a bug in one dispatch cycle
  doesn't take down the server.
- The API layer is stateless (all session state lives in the `auth_tokens` table, not
  in-process), so a crashed/restarted process loses no sessions.
- CI runs the full test suite on every single push/PR to `main` - no change reaches `main`
  without 183 tests passing first.

These are reasons to *expect* good reliability, not a measurement of it. A real answer to
this AC needs an actual deployment and a month of wall-clock time, neither of which exist
yet.

## 5. HMS-NF-003 / Security - not re-verified here, already covered elsewhere

Encrypted transmission and unauthorized-access rejection are already covered by the existing
`test_tls.py` (TLS 1.2+ enforcement) and the RBAC test suite spread across every router (every
protected endpoint has an explicit "wrong role → 403" test). Re-litigating those here would
just be re-running tests that already exist and already pass on every CI run; this report
doesn't duplicate them.

## Summary

| AC | Status |
|---|---|
| Audit logging (issue's SR-003, actually SR-004) | **Verified** - one real gap found (`EHR_VIEWED` missing) and fixed |
| NF-001 Performance | **Partially verified** - P90 6.54ms over 200 sequential requests; true 200-concurrent-user load testing out of reach without dedicated infrastructure |
| NF-004 Usability | **Not verified** - needs a real human-subjects study not run here |
| NF-002 Reliability/uptime | **Not verified** - needs a production deployment accumulating real monitoring data, which doesn't exist |
| NF-003 Security | Already covered by existing TLS/RBAC test suites, not re-verified in this report |

Honest reporting of what wasn't verified, and why, is itself the point of a verification
story - the alternative (claiming full coverage) would be worse than the gaps themselves.
