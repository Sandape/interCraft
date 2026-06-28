# REQ-033 US10 — Environment-Specific Redaction Policy + 30-Day Production Retention (T025-T033)

**Date**: 2026-06-28
**Branch**: `master` (REQ-033 active work)
**Scope**: US10 — environment-specific export policy + 30-day production retention
**Tester**: dev (autonomous batch)

## 1. Deliverables

| Task | Status | File | Lines | Notes |
|------|--------|------|------:|-------|
| T025 redaction tests | DONE | `backend/tests/integration/test_033_redaction_policy.py` | 344 | 31 tests: forbidden-content (5 parametrized), dual approval, fail-open, env routing. |
| T026 retention tests | DONE | `backend/tests/integration/test_033_production_retention.py` | 534 | 15 tests: 30-day window, dry-run override, staging 7-day archive, dev no-op. |
| T027 CLI contract tests | DONE | `backend/tests/contract/test_033_redaction_cli_contract.py` | 508 | 19 tests: exit codes (0/1/2/3), JSON shape, `--json`, warnings, two end-to-end subprocess invocations. |
| T028 redaction_cli.py | DONE | `backend/app/modules/telemetry_contracts/redaction_cli.py` | 360 | `python -m app.modules.telemetry_contracts.redaction_cli --environment ... --sample ... --out ... [--json]`. Pure `audit_samples()` + `render_markdown()` callable from tests. |
| T029 retention_cli.py | DONE | `backend/app/modules/telemetry_contracts/retention_cli.py` | 289 | `python -m app.modules.telemetry_contracts.retention_cli --environment ... [--json] [--dry-run]`. Pure `check_retention()` callable from tests; production always dry-run (FR-035a). |
| T030 export_policy.py | DONE | `backend/app/eval/export_policy.py` | 383 | `prepare_export_payload` / `enforce_export_policy` / `is_override_approved` / `safe_prepare_export_payload` (fail-open). LangSmith sync is documented as a future US6 hook point; no LangSmith import. |
| T031 fixtures | DONE | `backend/tests/integration/fixtures/033_redaction_samples.py` | 353 | `forbidden_resume_sample` / `forbidden_interview_answer_sample` / `forbidden_jd_sample` / `forbidden_secret_sample` / `forbidden_free_form_sample` / `approved_synthetic_sample` / `golden_case_sample` / `override_record_dual_signed` / `override_record_single_signed` + 9 pytest wrapper fixtures. |
| T032 template.md | DONE | `docs/evidence/033-eval-pm-dashboard/redaction-check-template.md` | 125 | Audit report format: top metadata + per-sample table + overall result + reviewer + generation instructions. |
| T033 this report | DONE | `test-reports/REQ-033-US10-test.md` | — | — |

**Pre-existing 033 surface preserved verbatim** (no breaking changes to
`telemetry_contracts/{redaction,retention,events,metrics,__init__}.py`):
all 51 foundation tests from T024 still pass.

## 2. pytest Result

```bash
$ cd backend && uv run pytest \
    tests/integration/test_033_redaction_policy.py \
    tests/integration/test_033_production_retention.py \
    tests/contract/test_033_redaction_cli_contract.py -v
```

```
======================== 65 passed, 1 warning in 1.06s ========================
```

Breakdown:

- `tests/integration/test_033_redaction_policy.py`: **31 passed**
  - 5 parametrized: production forbidden content (resume / interview / JD / free-form / secret) → audit fails
  - 2 production audit metadata tests
  - 1 validate_redaction flags properties
  - 1 production enforce_export_policy raises PolicyViolation
  - 4 staging / production default context tests
  - 3 non-prod forbidden content detection (find / strip / helper agreement)
  - 4 dual-approval gate tests (dual / single / only-technical / empty)
  - 2 fail-open runtime tests
  - 8 parametrized env routing tests
  - 1 JSON-serializability test

- `tests/integration/test_033_production_retention.py`: **15 passed**
  - 2 retention window tests (active / expired)
  - 2 retention check CLI shape (zero expired + JSON serialization)
  - 1 expired count + earliest trace id
  - 1 staging 7-day default
  - 1 staging 8-day expired
  - 1 dev default no-op
  - 1 dev store never reports expired (None retention_expires_at convention)
  - 1 production check always dry-run override
  - 1 production 30-day default
  - 2 next_cleanup_at cadence
  - 2 enforce_retention (production 30d / staging 7d boundary)

- `tests/contract/test_033_redaction_cli_contract.py`: **19 passed**
  - 3 happy-path / failure-path / list-of-samples aggregation
  - 4 exit-code matrix (missing file / unparseable / unknown env / no samples)
  - 2 `--json` flag shape
  - 4 retention CLI shape / aggregation / dry-run / staging max-age
  - 1 retention unknown env exit 2
  - 1 markdown template required sections
  - 2 valid environments subset
  - 2 end-to-end `python -m` subprocess invocations (regression / production check)

**Regression — pre-existing 033 tests still pass:**

```bash
$ cd backend && uv run pytest tests/unit/test_033_redaction.py \
    tests/unit/test_033_retention.py \
    tests/contract/test_033_event_metric_schema.py \
    tests/unit/test_033_metric_definitions.py \
    tests/unit/test_033_eval_runner_report.py
```

```
======================== 51 passed, 1 warning in 0.39s ========================
```

Combined: **65 new + 51 regression = 116 tests pass** for US10.

## 3. CLI Smoke Tests

### 3.1 Production fail (forbidden resume content)

```bash
$ cd backend && uv run python -m app.modules.telemetry_contracts.redaction_cli \
    --environment production \
    --sample /tmp/033-smoke/prod-fail.json \
    --out /tmp/033-smoke/prod-fail.md \
    --json --reviewer alice.pm
```

```json
{"auditId": "redaction-20260628-132152", "environment": "PRODUCTION",
 "policyVersion": "v1", "sampleCount": 1, "forbiddenContentFailures": 1,
 "result": "FAILED", "samples": [{"sampleId": "evt-prod-bad-001",
 "privacyClass": "PUBLIC_METADATA", "redactionStatus": "PENDING",
 "verdict": "FAILED", "violations": ["resume_text"],
 "notes": ["forbidden production content detected: ['resume_text']"]}],
 "reviewer": "alice.pm"}
EXIT=3
```

### 3.2 Staging pass (synthetic + approved staging test data)

```bash
$ cd backend && uv run python -m app.modules.telemetry_contracts.redaction_cli \
    --environment staging \
    --sample /tmp/033-smoke/staging-pass.json \
    --out /tmp/033-smoke/staging-pass.md --json
```

```json
{"auditId": "redaction-20260628-132202", "environment": "STAGING",
 "policyVersion": "v1", "sampleCount": 2, "forbiddenContentFailures": 0,
 "result": "PASSED", "samples": [
  {"sampleId": "evt-staging-ok-001", "verdict": "PASSED", "violations": []},
  {"sampleId": "evt-staging-ok-002", "verdict": "PASSED", "violations": []}]}
EXIT=0
```

### 3.3 Production pass (redacted summary only)

```bash
$ cd backend && uv run python -m app.modules.telemetry_contracts.redaction_cli \
    --environment production \
    --sample /tmp/033-smoke/prod-pass-summary.json \
    --out /tmp/033-smoke/prod-pass-summary.md --json
```

```json
{"auditId": "redaction-20260628-132218", "environment": "PRODUCTION",
 "policyVersion": "v1", "sampleCount": 1, "forbiddenContentFailures": 0,
 "result": "PASSED", "samples": [{"sampleId": "evt-prod-summary-001",
 "privacyClass": "REDACTED_SUMMARY", "redactionStatus": "PASSED",
 "verdict": "PASSED", "violations": []}]}
EXIT=0
```

### 3.4 Retention check (production, dry-run)

```bash
$ cd backend && uv run python -m app.modules.telemetry_contracts.retention_cli \
    --environment production --json
```

```json
{"environment": "PRODUCTION", "checkedRows": 0, "expiredCount": 0,
 "earliestExpiredAt": null, "earliestTraceId": null, "dryRun": true,
 "policyVersion": "v1",
 "nextCleanupAt": "2026-06-29T13:22:26.711817+00:00",
 "policyAction": "delete", "maxAgeDays": 30,
 "timestamp": "2026-06-28T13:22:26.711817+00:00"}
EXIT=0
```

Notes:

- The `_load_rows_from_store()` placeholder returns an empty list. The
  CLI contract (exit codes, JSON shape, `dryRun: true` for production)
  is fully exercised; Sub-batch 2 wires the SQLAlchemy repository fetch.
- `dryRun: true` confirms FR-035a — production never auto-deletes.

## 4. mypy Result

```bash
$ cd backend && uv run mypy app/modules/telemetry_contracts/ \
    app/eval/export_policy.py 2>&1 | tail -30
```

```
Success: no issues found in 10 source files
```

10 files covered: `events.py`, `metrics.py`, `redaction.py`, `retention.py`,
`models.py`, `repository.py`, `__init__.py`, `redaction_cli.py`,
`retention_cli.py`, `eval/export_policy.py`.

## 5. SC-008 Verification (Production zero forbidden content)

SC-008: *"Production export privacy audit finds zero raw resumes,
interview answers, job descriptions, free-form user text, or secrets in
exported production payload samples before production export is
enabled."*

Verified by the parametrized test
`test_production_forbidden_content_blocks_export[resume_text|interview_answer|job_description|free_form|secret]`:

```text
tests/integration/test_033_redaction_policy.py::test_production_forbidden_content_blocks_export[resume_text] PASSED
tests/integration/test_033_redaction_policy.py::test_production_forbidden_content_blocks_export[interview_answer] PASSED
tests/integration/test_033_redaction_policy.py::test_production_forbidden_content_blocks_export[job_description] PASSED
tests/integration/test_033_redaction_policy.py::test_production_forbidden_content_blocks_export[free_form] PASSED
tests/integration/test_033_redaction_policy.py::test_production_forbidden_content_blocks_export[secret] PASSED
```

For each forbidden category the audit returns:

- `payload=None` (production hard-rejects)
- `redaction_status="FAILED"`
- non-empty `violations` list

The companion happy-path test
`test_redaction_cli_passed_produces_exit_0_and_json_shape` confirms
that production payloads WITHOUT forbidden content pass the audit
with `forbiddenContentFailures=0` and `result=PASSED`.

## 6. Hard Constraints Audit

| Constraint | Status |
|---|---|
| **fail-open runtime (FR-017)** | PASS — `safe_prepare_export_payload` swallows unexpected exceptions and returns `RedactionResult(payload=None, redaction_status="FAILED")`. Covered by `test_fail_open_when_prepare_raises_unexpected` + `test_fail_open_returns_failed_status_not_raises`. |
| **no breaking change to telemetry_contracts public API** | PASS — 51 foundation tests still pass. `redaction.py` / `retention.py` / `events.py` / `metrics.py` / `__init__.py` untouched. |
| **no 501 stubs** | PASS — `retention_cli._load_rows_from_store` is a documented Sub-batch 2 hook with a comment, not a 501 stub. It returns `[]` so the CLI contract still produces the canonical JSON envelope. |
| **no LangSmith import** | PASS — `export_policy.py` imports only from `app.modules.telemetry_contracts.redaction` + stdlib. The docstring documents the US6 LangSmith sync hook point. |
| **scope strict (US10 only)** | PASS — no US1/US5/US8/US9 code touched. |
| **dual approval hard fail** | PASS — `is_override_approved` requires BOTH PM_BUSINESS_OWNER + TECHNICAL_OWNER; `assert_override_approved` raises `PolicyViolation("missing_dual_approval")` otherwise. |
| **production forbidden-content detection** | PASS — 9 forbidden keys (`resume_text`, `interview_answer`, `job_description`, `free_form_text`, `api_key`, `access_token`, `refresh_token`, `password`, `secret`); case-insensitive; walks `properties` + `metadata` + top-level. |
| **production dry-run override (FR-035a)** | PASS — `check_retention` always returns `dry_run=True` for production regardless of caller intent. Covered by `test_retention_cli_production_always_dry_run` + `test_production_check_always_dry_run_even_if_requested_otherwise`. |

## 7. Deviations / Follow-up Items

| # | Item | Owner | When |
|---|---|---|---|
| D1 | `retention_cli._load_rows_from_store()` returns `[]`. Sub-batch 2 must wire this to the SQLAlchemy `TraceRunRef` table via `app.modules.telemetry_contracts.repository`. The CLI contract (exit codes, JSON shape, `dryRun: true`) is fully exercised by the integration tests. | dev | US9 / Sub-batch 2 |
| D2 | `redaction_cli` is exposed at `app.modules.telemetry_contracts.redaction_cli` (matches filesystem layout). The spec contract doc lists `app.telemetry_contracts.redaction audit` (no `modules.`) — discrepancy is documentation, not code. The CLI invocation in `docs/evidence/.../redaction-check-template.md` uses the actual module path. | reviewer | next doc refresh |
| D3 | US6 LangSmith sync (`langsmith_reporter.py`) is not implemented; `export_policy.py` exposes `prepare_export_payload` / `enforce_export_policy` as the contract surface for US6 to call. No LangSmith import was added. | dev | US6 |
| D4 | `test_redaction_cli_failed_production_exits_3` asserts `forbiddenContentFailures >= 1`. Tightening to `== 1` is left as future refinement when multi-violation scenarios become first-class. | dev | next round |
| D5 | No 30-day delete worker was implemented in this batch. The CLI is dry-run only (FR-035a). The actual deletion flow (operator-triggered, with audit row) is Sub-batch 2 work. | dev | Sub-batch 2 |

## 8. Files Touched

```
backend/app/modules/telemetry_contracts/redaction_cli.py      +360 (new)
backend/app/modules/telemetry_contracts/retention_cli.py       +289 (new)
backend/app/eval/export_policy.py                              +383 (new)
backend/tests/integration/fixtures/033_redaction_samples.py    +353 (new)
backend/tests/integration/test_033_redaction_policy.py         +344 (new)
backend/tests/integration/test_033_production_retention.py     +534 (new)
backend/tests/contract/test_033_redaction_cli_contract.py      +508 (new)
docs/evidence/033-eval-pm-dashboard/redaction-check-template.md +125 (new)
test-reports/REQ-033-US10-test.md                              (this file, new)
```

No existing files were modified. The pre-existing 033 surface (events.py,
metrics.py, redaction.py, retention.py, models.py, repository.py,
__init__.py, README.md, foundation test files) is preserved verbatim.

## 9. Success Criteria Coverage

| SC | Coverage |
|---|---|
| SC-005 100% prompt-adjacent PR eval failures include identifiers | Not US10 scope; US5 work. |
| SC-008 zero forbidden production content in exported samples | **VERIFIED** — 5 parametrized tests + happy-path test. |
| SC-014 100% production trace records deleted after 30 days | Covered structurally: `_retention_check` enumerates `retention_expires_at < now`; production dry-run override forces manual review. DB wire-up deferred to Sub-batch 2. |
| SC-013 100% emergency overrides dual approval | **VERIFIED** — `is_override_approved` requires both PM + technical; single-signer hard-fails. |
| FR-017 LangSmith fail-open for product runtime | **VERIFIED** — `safe_prepare_export_payload` swallows exceptions. |
| FR-031..FR-036 export policy | **VERIFIED** — `enforce_export_policy` + `prepare_export_payload`. |
| FR-035a 30-day production retention | **VERIFIED** — `production_default_context()` returns `max_age_days=30` + `action="delete"`. CLI default is dry-run. |
| FR-024 dual approval (PM + technical owner) | **VERIFIED** — `assert_override_approved` raises on missing dual sign-off. |