# Contract: LLM Ops CLI

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

CLI commands are the canonical local and CI automation surface for REQ-045.
Commands below define interface semantics only; implementation is produced by
later tasks.

## Shared Rules

- Default output is human-readable.
- `--json` emits machine-readable JSON to stdout.
- Warnings and non-fatal integration failures go to stderr.
- Exit `0`: success.
- Exit `1`: operational failure.
- Exit `2`: invalid arguments.
- Exit `3`: policy/authorization violation.
- Exit `4`: eval gate failed.
- Local eval verdicts are never changed by LangSmith/OTLP export status.

## Eval Run

```text
python -m app.eval.cli run \
  --suite golden \
  --env ci \
  --source-revision <git-sha> \
  --branch <branch> \
  --report-out docs/evidence/<run_id>/eval-report.json \
  --markdown-out docs/evidence/<run_id>/eval-report.md \
  --sync-langsmith auto \
  --json
```

`--sync-langsmith` values:

- `never`: do not attempt LangSmith sync.
- `auto`: sync when enabled and credentials/policy are present.
- `require`: fail with exit `1` if LangSmith sync cannot complete.

Required JSON output:

```json
{
  "runId": "7b95b3c3-3f31-4097-8982-4dc3f8f455c0",
  "status": "PASSED",
  "sourceRevision": "abc123",
  "branch": "codex/045-llm-ops-eval-workflow",
  "environment": "CI",
  "datasetVersion": "golden-v2",
  "aggregatePassRate": 1.0,
  "knownRegressionRecall": 1.0,
  "langsmithExportStatus": "SYNCED",
  "artifacts": {
    "json": "docs/evidence/<run_id>/eval-report.json",
    "markdown": "docs/evidence/<run_id>/eval-report.md"
  }
}
```

Gate behavior:

- Deterministic golden-case failures exit `4`.
- Nightly budget exhaustion exits `1` with status `INCOMPLETE`.
- LangSmith sync failure exits `0` in `auto` mode when local eval passed, with
  `langsmithExportStatus: "FAILED"`.

## LangSmith Sync

```text
python -m app.eval.cli langsmith-sync \
  --report docs/evidence/<run_id>/eval-report.json \
  --project intercraft-production \
  --destination-policy production-langsmith-full-content-v1 \
  --json
```

Required JSON output:

```json
{
  "runId": "7b95b3c3-3f31-4097-8982-4dc3f8f455c0",
  "syncStatus": "SYNCED",
  "project": "intercraft-production",
  "dataset": "intercraft-agent-golden-v2",
  "experimentName": "045-abc123-golden-v2",
  "url": "https://smith.langchain.com/o/example/projects/p/r/...",
  "exportPolicyDecisionId": "epd_01J..."
}
```

Disabled behavior:

- If LangSmith is disabled, exits `0` with `syncStatus: "DISABLED"`.
- If upload fails, exits `1` with `syncStatus: "FAILED"`.
- If full-content policy is required but missing, exits `3`.

## Export Policy Audit

```text
python -m app.eval.cli export-audit \
  --destination langsmith \
  --environment production \
  --representation full_content \
  --sample docs/evidence/<run_id>/export-sample.json \
  --out docs/evidence/<run_id>/export-policy-audit.md \
  --json
```

Required JSON output:

```json
{
  "decisionId": "epd_01J...",
  "destination": "LANGSMITH",
  "environment": "PRODUCTION",
  "representationLevel": "FULL_CONTENT",
  "policyVersion": "production-langsmith-full-content-v1",
  "owner": "ai-platform",
  "accessScope": "ai-ops-debuggers",
  "retentionDays": 30,
  "result": "PASSED",
  "evidenceRef": "docs/evidence/<run_id>/export-policy-audit.md"
}
```

Failure behavior:

- Missing full-content production policy exits `3`.
- Operational secrets in any export sample exit `3`.
- Non-approved destinations with raw AI payloads exit `3`.

## Judge Run

```text
python -m app.eval.cli judge-run \
  --report docs/evidence/<run_id>/eval-report.json \
  --rubric specs/045-llm-ops-eval-workflow/rubrics/coaching-quality-v1.json \
  --json
```

Output includes `judgeVerdictCount`, `blockingVerdictCount`, rubric version,
judge model, and artifact references.

Rules:

- Uncalibrated rubrics are report-only.
- Judge execution failure is an operational failure for the judge command, but
  does not retroactively change deterministic eval verdicts.

## Judge Calibration

```text
python -m app.eval.cli judge-calibrate \
  --rubric specs/045-llm-ops-eval-workflow/rubrics/coaching-quality-v1.json \
  --labels specs/045-llm-ops-eval-workflow/calibration/coaching-quality-labels.jsonl \
  --json
```

Required JSON output:

```json
{
  "rubricId": "coaching-quality",
  "rubricVersion": "v1",
  "humanLabelCount": 30,
  "agreementRate": 0.83,
  "calibrationStatus": "CALIBRATED",
  "canBlockMerges": true
}
```

## Experiment Compare

```text
python -m app.eval.cli experiment-compare \
  --baseline-run <run_id> \
  --candidate-run <run_id> \
  --out docs/evidence/<candidate_run_id>/experiment-compare.json \
  --json
```

Output includes pass-rate delta, known-regression delta, judge-score delta,
cost delta, latency delta, confidence warnings, and recommendation.

## Badcase Promotion

```text
python -m app.modules.badcases.cli promote \
  --badcase-id <badcase_id> \
  --target-suite golden \
  --reviewer <user> \
  --export-policy-decision <decision_id> \
  --reason "protect production regression" \
  --json
```

Rules:

- Produces a `CANDIDATE` or `REPORT_ONLY` case first.
- Does not auto-refresh golden baseline.
- Requires human reviewer metadata.

## Prompt Proposal

```text
python -m app.eval.cli prompt-proposal create \
  --from-run <run_id> \
  --case-cluster <cluster_id> \
  --target-node interview.score_llm \
  --json
```

```text
python -m app.eval.cli prompt-proposal compare \
  --proposal <proposal_id> \
  --baseline-run <run_id> \
  --candidate-run <run_id> \
  --json
```

```text
python -m app.eval.cli prompt-proposal approve \
  --proposal <proposal_id> \
  --approver <user> \
  --evidence docs/evidence/<run_id>/experiment-compare.json \
  --json
```

Rules:

- Approval requires comparison evidence.
- No command may auto-deploy a prompt or auto-refresh a golden baseline.
