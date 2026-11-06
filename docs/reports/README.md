# Testing Reports

Generated 2026-11-05 against `main` (+ pending alignment PRs #45/#46). All reproducible with
one command each - see each report for its exact command.

| Report | What it covers |
|---|---|
| [Unit Test Report](unit_test_report.md) | All 197 automated tests, one file per user story, 21/21 stories covered |
| [System Validation Report](system_validation_report.md) | A real, live, end-to-end run of the full hospital workflow across 13 stories - not a pytest file, a standalone script hitting a running server over real HTTP |
| [Code Coverage Report](code_coverage_report.md) | Statement coverage: 96% overall, per-module breakdown, and an honest explanation of every real gap |
| [Branch Coverage Report](branch_coverage_report.md) | Branch coverage: 87% overall (the stricter metric - did every `if`/`else` take both paths), per-module breakdown |
| [`coverage_html/`](coverage_html/index.html) | The full interactive `coverage.py` HTML report - click into any file to see exactly which lines/branches ran |
| [`coverage.xml`](coverage.xml) | Machine-readable coverage data (Cobertura format) |
| [`junit_results.xml`](junit_results.xml) | Machine-readable test results (JUnit XML) |

See also [`../test-results/`](../test-results/) for story-specific manual test execution
records (test-by-test pass/fail tables with expected vs. actual results) written during
Sprint 1 and Sprint 2, and [`../../backend/NFR_VERIFICATION.md`](../../backend/NFR_VERIFICATION.md)
for the non-functional-requirements verification pass (performance, reliability, usability,
audit logging).
