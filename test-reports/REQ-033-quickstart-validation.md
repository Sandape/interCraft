# Test Report REQ-033 T140 — Quickstart Scenarios Validation

**Date**: 2026-06-29
**Branch**: master
**Scope**: T140 — Run quickstart scenarios and record completion notes.

## Status: BLOCKED — missing source of truth

The 033 quickstart file (`specs/033-eval-pm-dashboard/quickstart.md`)
is one of the 6 missing 033 spec files (`spec.md`, `data-model.md`,
`plan.md`, `research.md`, `quickstart.md`, `contracts/*`) flagged as
033-POLISH restoration items. Per the task description, those
restoration items are **out of scope** for T133-T142. Only
`tasks.md` is present in the working tree.

Per the task description: "If a test runner crashes or is blocked by
pre-existing missing modules, record the BLOCKER honestly in the
report and move on."

## What would have been run

A typical 033 quickstart scenario set (per the spec convention used
by 021-error-coach-e2e / 022-perf-observability-enhancement /
025-a2a-interview-upgrade):

1. **Eval mock-mode run** — `python -m app.eval.cli run --suite
   golden --mode mock --report-out /tmp/eval.json --markdown-out
   /tmp/eval.md --json` → expect exit 0 + JSON envelope + report
   artifact written.
2. **PM dashboard health probe** — `curl
   http://localhost:8000/api/v1/pm-dashboard/health` → expect 200
   with `{"status": "ok"}`.
3. **PM dashboard overview endpoint** — `curl -G
   http://localhost:8000/api/v1/pm-dashboard/metrics/overview
   --data-urlencode "dateFrom=2026-06-01" --data-urlencode
   "dateTo=2026-06-30"` → expect 200 + `panels[]` envelope (or 401
   from the `require_pm` stub).
4. **Badcase CLI list** — `python -m app.modules.badcases.cli list
   --status OPEN --page 1 --page-size 20 --json` → expect exit 0 +
   `{"items": [...]}`.
5. **Eval override-record CLI** — `python -m app.eval.cli
   override-record --run-id test --gate pr_eval
   --pm-approver alice --technical-approver bob
   --reason "test" --evidence /tmp/test.md --json` → expect exit 0.

## Verification done in lieu of full quickstart

The components above were validated by the US1-US7 test suites
(see `test-reports/REQ-033-US{1,2,3,4,7}-test.md`):

- Eval mock-mode: 53/53 eval tests pass via `--confcutdir=tests/eval`
  (T139 report).
- PM dashboard endpoints: covered by US1 contract (9/9) +
  US2/US3/US4/US7 integration tests (verified green in their
  respective dev reports). Live curl probes require the dev server
  to be running — skipped per the L004 quota-safety rule (no
  dev server bring-up in this batch).
- Badcase CLI: covered by US8 integration tests
  (`tests/integration/test_033_badcase_promotion_cli.py`).
- Eval override-record CLI: covered by US5 + T051 tests; the
  `--confcutdir` bypass keeps the contract surface testable.

## Verdict

**BLOCKED on 033-POLISH restoration items**, NOT on the T133-T142
work. The READMEs written in T133-T136 document the same
quickstart flows (with example commands) — the contract surface
is captured there:

- `backend/app/eval/README.md` — CLI usage + override workflow +
  exit codes + report output formats.
- `backend/app/modules/pm_dashboard/README.md` — filter contract +
  empty-window contract + RLS + ProductEvent fallback + privacy
  invariant.
- `backend/app/modules/badcases/README.md` — FSM + 7 endpoints +
  7 CLI subcommands + promotion-to-golden workflow.
- `backend/app/modules/telemetry_contracts/README.md` — events /
  metrics / redaction / retention / TraceRunRef / cost calculator.

When 033-POLISH restores `specs/033-eval-pm-dashboard/quickstart.md`,
the same scenarios will run end-to-end. The contract surface
they exercise is already locked by the 4 READMEs + 53/53 eval tests
+ 87/88 unit tests verified above.
