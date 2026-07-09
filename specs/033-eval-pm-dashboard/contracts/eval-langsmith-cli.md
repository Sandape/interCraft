# Contract: Eval, LangSmith Sync, Redaction, And Badcase CLI

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

The first MVP month must be operable from CLI for CI and badcase promotion.
Commands below define interface semantics only; implementation belongs to tasks.

## Shared CLI Rules

- Default output is human-readable.
- `--json` emits machine-readable JSON to stdout.
- Warnings go to stderr.
- Exit `0`: success.
- Exit `1`: operational failure.
- Exit `2`: invalid arguments.
- Exit `3`: policy/redaction violation.
- Exit `4`: eval gate failed.

## Eval Run

```text
python -m app.eval.cli run \
  --suite golden \
  --report-out docs/evidence/<run_id>/eval-report.json \
  --markdown-out docs/evidence/<run_id>/eval-report.md \
  --env ci \
  --json
```

Required JSON output:

```json
{
  "runId": "run-20260626-001",
  "status": "PASSED",
  "sourceRevision": "abc123",
  "branch": "feature",
  "environment": "CI",
  "aggregatePassRate": 1.0,
  "knownRegressionRecall": 1.0,
  "staleCaseCount": 0,
  "artifacts": {
    "json": "docs/evidence/run/eval-report.json",
    "markdown": "docs/evidence/run/eval-report.md"
  }
}
```

Gate behavior:

- Deterministic prompt-adjacent failures exit `4`.
- Nightly real-model budget exhaustion exits `1` with status `INCOMPLETE`.
- LangSmith sync failure never changes local eval verdict.

## LangSmith Sync

```text
python -m app.eval.cli langsmith-sync \
  --report docs/evidence/<run_id>/eval-report.json \
  --project intercraft-ci \
  --json
```

Required JSON output:

```json
{
  "runId": "run-20260626-001",
  "syncStatus": "SYNCED",
  "project": "intercraft-ci",
  "dataset": "intercraft-interview-score-golden-v1",
  "experimentName": "run-20260626-001-feature-abc123",
  "url": "https://..."
}
```

Disabled behavior:

- If LangSmith is disabled, command exits `0` with `syncStatus: "DISABLED"`.
- If upload fails, command exits `1` with `syncStatus: "FAILED"` and an error
  message; local report remains canonical.

## Redaction Audit

```text
python -m app.telemetry_contracts.redaction audit \
  --environment production \
  --sample docs/evidence/<run_id>/export-sample.json \
  --out docs/evidence/<run_id>/redaction-check.md \
  --json
```

Required JSON output:

```json
{
  "auditId": "redaction-20260626-001",
  "environment": "PRODUCTION",
  "policyVersion": "v1",
  "sampleCount": 20,
  "forbiddenContentFailures": 0,
  "result": "PASSED",
  "evidenceRef": "docs/evidence/run/redaction-check.md"
}
```

Failure behavior:

- Any raw production resume, interview answer, JD text, free-form text, or secret
  exits `3`.
- Runtime/product execution is never blocked by export failure.

## PM Metric Snapshot

```text
python -m app.modules.pm_dashboard.cli snapshot \
  --date-from 2026-06-01 \
  --date-to 2026-07-01 \
  --environment staging \
  --json
```

Output includes metric ids, values, source of truth, freshness, and quality
flags. Missing version fields must be explicit `unknown`, never omitted.

## Badcase Review And Promotion

```text
python -m app.modules.badcases.cli create \
  --source eval_failure \
  --run-id <run_id> \
  --case-id <case_id> \
  --type eval_regression \
  --severity high \
  --json
```

```text
python -m app.modules.badcases.cli promote \
  --badcase-id <id> \
  --reviewer <user> \
  --redaction-audit <audit_id> \
  --reason "protect regression" \
  --json
```

Promotion rules:

- Requires reviewer identity.
- Requires redaction status `PASSED` for any user-derived content.
- Produces a golden-case candidate, not an automatic baseline refresh.
- First-month workflow is CLI/documented; admin UI is out of MVP scope.

## Baseline Refresh / Emergency Override Record

```text
python -m app.eval.cli override-record \
  --run-id <run_id> \
  --gate pr_eval \
  --pm-approver <name> \
  --technical-approver <name> \
  --reason "<short reason>" \
  --evidence <path-or-url> \
  --json
```

Rules:

- Both PM business owner and technical owner are required.
- Records must include reason, evidence, timestamp, affected gate or baseline.
