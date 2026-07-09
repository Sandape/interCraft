# Quickstart: REQ-045 LLM Ops Eval Workflow

This guide describes validation scenarios after implementation. Commands are
written from the repository root unless stated otherwise.

## Prerequisites

- Backend environment can run `cd backend && uv run pytest -q`.
- Frontend environment can run `npm run typecheck` and `npm run test`.
- LangSmith credentials are optional. Disabled behavior must work without them.
- Production full-content LangSmith validation requires an explicit destination
  policy fixture or environment configuration.

## 1. Validate Local Eval With LangSmith Disabled

```bash
cd backend
uv run python -m app.eval.cli run \
  --suite golden \
  --env ci \
  --source-revision local-dev \
  --branch 045-llm-ops-eval-workflow \
  --sync-langsmith never \
  --report-out ../docs/evidence/045-local/eval-report.json \
  --markdown-out ../docs/evidence/045-local/eval-report.md \
  --json
```

Expected:

- Exit `0` when deterministic cases pass, or `4` when golden cases fail.
- JSON and Markdown artifacts are written.
- Case results include `runId`, `traceId` or `"unavailable"`, `artifactRef`,
  and `langsmithUrl: "unavailable"`.
- No network dependency is required.

## 2. Validate Trace Correlation

```bash
cd backend
uv run pytest \
  tests/integration/test_045_trace_correlation.py \
  app/agents/tests/test_045_llm_invocation_trace_ids.py \
  -q
```

Expected:

- Covered workflow records share run id and trace id across logs, spans, LLM
  invocation records, and eval artifacts.
- Missing trace ids are counted as coverage failures.
- Export backend failure does not fail the AI workflow.

## 3. Validate Production Full-Content LangSmith Policy

```bash
cd backend
uv run python -m app.eval.cli export-audit \
  --destination langsmith \
  --environment production \
  --representation full_content \
  --sample ../docs/evidence/045-local/export-sample.json \
  --out ../docs/evidence/045-local/export-policy-audit.md \
  --json
```

Expected:

- Audit passes only when full-content LangSmith policy metadata is present.
- Raw AI payloads are allowed for LangSmith under that policy.
- Operational secrets, access tokens, credentials, and infrastructure passwords
  fail the audit.

## 4. Validate LangSmith Sync

```bash
cd backend
uv run python -m app.eval.cli langsmith-sync \
  --report ../docs/evidence/045-local/eval-report.json \
  --project intercraft-ci \
  --destination-policy production-langsmith-full-content-v1 \
  --json
```

Expected:

- With credentials and policy: `syncStatus: "SYNCED"` and a LangSmith URL.
- Without credentials: `syncStatus: "DISABLED"` when disabled by config.
- Failed sync does not modify local report verdict.

## 5. Validate Judge Calibration And Report-Only Behavior

```bash
cd backend
uv run python -m app.eval.cli judge-calibrate \
  --rubric ../specs/045-llm-ops-eval-workflow/rubrics/coaching-quality-v1.json \
  --labels ../specs/045-llm-ops-eval-workflow/calibration/coaching-quality-labels.jsonl \
  --json
```

Expected:

- Rubrics with fewer than 30 labels or agreement below 80% remain report-only.
- Calibrated rubrics record label count, agreement rate, judge model, and
  rubric version.

## 6. Validate Experiment Comparison

```bash
cd backend
uv run python -m app.eval.cli experiment-compare \
  --baseline-run <baseline_run_id> \
  --candidate-run <candidate_run_id> \
  --out ../docs/evidence/045-local/experiment-compare.json \
  --json
```

Expected:

- Comparison includes quality, known-regression, cost, latency, judge-score, and
  confidence fields.
- Comparison refuses incompatible dataset versions unless marked exploratory.

## 7. Validate Badcase Promotion

```bash
cd backend
uv run python -m app.modules.badcases.cli promote \
  --badcase-id <badcase_id> \
  --target-suite golden \
  --reviewer <user> \
  --export-policy-decision <decision_id> \
  --reason "protect production regression" \
  --json
```

Expected:

- Promotion creates a candidate/report-only eval case first.
- Candidate cannot block merges until accepted as golden.
- Source badcase, trace, artifact, reviewer, and policy decision are recorded.

## 8. Validate Prompt Proposal Guardrail

```bash
cd backend
uv run python -m app.eval.cli prompt-proposal create \
  --from-run <run_id> \
  --case-cluster <cluster_id> \
  --target-node interview.score_llm \
  --json
```

Expected:

- Proposal is created as `DRAFT` or `READY_FOR_COMPARISON`.
- It cannot be approved without baseline/candidate comparison evidence.
- It cannot auto-deploy a prompt or auto-refresh a golden baseline.

## 9. Validate API Contracts

```bash
cd backend
uv run pytest tests/contract/test_045_ai_ops_api.py -q
```

Expected:

- List endpoints are paginated.
- Errors use the shared error shape.
- Eval run detail exposes local artifacts, trace references, LangSmith refs,
  export policy decisions, and judge verdict summaries.

## 10. Full Regression Sweep

Run the relevant canonical checks before marking any requirement done:

```bash
cd backend && uv run pytest -q
npm run typecheck
npm run test
```

Add `npm run e2e` when admin/PM visible flows change.
