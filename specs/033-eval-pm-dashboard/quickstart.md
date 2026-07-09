# Quickstart: Validate REQ-033 Automated Eval & PM Dashboard MVP

**Spec**: [./spec.md](./spec.md) | **Plan**: [./plan.md](./plan.md)

This quickstart is a validation guide for future implementation. It does not
assume the code exists yet.

## Prerequisites

- Backend dependencies installed with `uv`.
- Frontend dependencies installed with `npm install`.
- Optional LangSmith credentials configured only for local/CI/staging tests that
  are approved for upload.
- Production export disabled until redaction, sampling, retention, and review
  evidence pass.

## Scenario 1: Local Deterministic Eval Report

Command:

```powershell
cd backend
uv run pytest tests/eval -q
uv run python -m app.eval.cli run --suite golden --env local --json
```

Expected:

- Eval report includes `runId`, source revision, branch, graph, node, case id,
  schema version, prompt fingerprint, rubric version, model, and verdicts.
- Local JSON/Markdown artifacts are readable without LangSmith access.
- Deterministic failures identify case id and failure reason.

## Scenario 2: LangSmith Disabled Path

Command:

```powershell
cd backend
$env:LANGSMITH_TRACING = "false"
uv run python -m app.eval.cli run --suite golden --env ci --json
```

Expected:

- Local eval pass/fail is authoritative.
- LangSmith sync is skipped or reports `DISABLED`.
- No external upload is required.

## Scenario 3: LangSmith Enabled Sync

Command:

```powershell
cd backend
$env:LANGSMITH_TRACING = "true"
$env:LANGSMITH_API_KEY = "<provided-by-user>"
uv run python -m app.eval.cli run --suite golden --env ci --json
uv run python -m app.eval.cli langsmith-sync --report docs/evidence/<run_id>/eval-report.json --project intercraft-ci --json
```

Expected:

- LangSmith experiment and local report share `runId` and source revision.
- Uploadable cases only include approved synthetic/golden data.
- Sync failure does not change the local eval verdict.

## Scenario 4: Nightly Budget Guard

Command:

```powershell
cd backend
uv run python -m app.eval.cli run --suite golden --env ci --real-model --nightly --json
```

Expected:

- Run respects about 5M tokens or $50 per night and $1000 monthly cap.
- Budget exhaustion marks the run incomplete and report-only.
- No baseline refresh occurs without PM business owner + technical owner
  approval.

## Scenario 5: Redaction Audit

Command:

```powershell
cd backend
uv run python -m app.telemetry_contracts.redaction audit --environment production --sample docs/evidence/<run_id>/export-sample.json --out docs/evidence/<run_id>/redaction-check.md --json
```

Expected:

- Any raw production resume, interview answer, JD text, free-form text, or
  secret fails the audit.
- Passing audit records policy version, sample count, reviewer, and evidence.
- Product runtime is not blocked by export failure.

## Scenario 6: PM Dashboard Contract

Command:

```powershell
cd backend
uv run pytest tests/contract/test_033_pm_dashboard_contract.py -q
cd ..
npm run test -- --run PMDashboard
```

Expected:

- Dashboard endpoints accept shared filters and return the contract envelope.
- Metrics include freshness and quality flags.
- Missing version fields appear as explicit `unknown`.
- Cost fields are labeled estimates.

## Scenario 7: Badcase Promotion CLI

Command:

```powershell
cd backend
uv run python -m app.modules.badcases.cli create --source eval_failure --run-id <run_id> --case-id <case_id> --type eval_regression --severity high --json
uv run python -m app.modules.badcases.cli promote --badcase-id <id> --reviewer <user> --redaction-audit <audit_id> --reason "protect regression" --json
```

Expected:

- Badcase records source, type, severity, reviewer, privacy class, and evidence.
- Promotion requires passed redaction status for user-derived content.
- Promotion creates a golden-case candidate; it does not refresh baseline.
- No admin UI is required in the first MVP month.

## Scenario 8: Production Retention Check

Command:

```powershell
cd backend
uv run python -m app.telemetry_contracts.retention check --environment production --json
```

Expected:

- Production trace metadata/redacted-summary records older than 30 days are
  deleted or inaccessible.
- Retention failures are reported for human review.

## Full Validation Commands

```powershell
npm run typecheck
npm run test
npm run build
cd backend
uv run pytest tests/eval -q
uv run pytest tests/contract -q
uv run pytest -q
```
