# `app.eval` — Eval reporting (REQ-033 US5 / US7)

Canonical eval runner, golden-case loader, JSON + Markdown report
rendering, export policy enforcement, and dual-approval override
recording for the InterCraft eval loop.

## Module map

| File | Purpose |
|------|---------|
| `runner.py` | `EvalRunner.run_all()` async pipeline. Per-case execution against mock or real LLM, retry policy, budget guard (nightly mode), and the canonical `EvalReport` dataclass. |
| `report.py` | `render_json_report()` + `render_markdown_report()`. Top-level JSON shape is stable across runs (CI artifact diffing). Markdown is human-readable with 6 sections (Header / Summary / Per-case verdicts / Debug identifiers / Failed-case drilldown / Aggregate stats). |
| `cli.py` | `python -m app.eval.cli run` + `override-record` subcommands. Exit codes 0 / 1 / 2 / 3 / 4 per `contracts/eval-langsmith-cli.md`. |
| `golden_loader.py` | Loads `golden/*.json` cases from the spec dir (default `specs/026-agent-eval-loop/`). Each case carries `node` / `status` (active / stale) / `inputs` / `expected`. |
| `export_policy.py` | `PolicyViolation` exception type + `check_export_allowed(environment)` decision function. Production = PII-redaction mandatory; staging = PII-redaction recommended; dev = no-op. |
| `prompt_fingerprint.py` | Deterministic SHA-256 of the system prompt + user inputs. Lets eval reports correlate failures to prompt changes. |
| `checker.py` | Per-case assertion helpers (string match / regex / JSON shape / numeric tolerance). The runner reads the `expected.kind` field to pick the right checker. |
| `__init__.py` | Re-exports `run_eval_suite` + `EvalReport` for ergonomic imports. |

## CLI usage

### Run the eval suite

```bash
# Mock-mode (default — no LLM quota burned)
uv run python -m app.eval.cli run \
    --suite golden \
    --report-out docs/evidence/run-001/eval-report.json \
    --markdown-out docs/evidence/run-001/eval-report.md \
    --env ci \
    --source-revision $(git rev-parse --short HEAD) \
    --branch $(git rev-parse --abbrev-ref HEAD) \
    --json

# Real-model nightly (burns quota — uses --nightly + --real-model)
uv run python -m app.eval.cli run \
    --suite nightly \
    --real-model --nightly \
    --budget-tokens 100000 \
    --budget-cost-usd 5.00 \
    --report-out docs/evidence/nightly-$(date +%Y%m%d)/eval-report.json \
    --markdown-out docs/evidence/nightly-$(date +%Y%m%d)/eval-report.md \
    --env production \
    --json

# Filter by node (debug a single graph node)
uv run python -m app.eval.cli run \
    --node interview.score \
    --report-out /tmp/interview-score-eval.json \
    --markdown-out /tmp/interview-score-eval.md
```

### Override-record (dual approval)

```bash
# Record an emergency override for a failed gate
uv run python -m app.eval.cli override-record \
    --run-id $(jq -r .runId eval-report.json) \
    --gate emergency_override \
    --pm-approver "alice@intercraft.io" \
    --technical-approver "bob@intercraft.io" \
    --reason "Hotfix — known regression from feature 027 cached prompt change. Tracking in JIRA-1234." \
    --evidence "docs/evidence/run-001/eval-report.md" \
    --json
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All active cases passed. |
| 1 | Operational failure (e.g. nightly budget exhausted → `INCOMPLETE` status report still written). |
| 2 | Invalid arguments (bad flag, missing `--report-out`/`--markdown-out`/`--json`). |
| 3 | Policy violation (missing dual approval, evidence URL points to loopback/private IP, evidence path traversal). |
| 4 | Eval gate failed (deterministic prompt-adjacent failure, ≥1 active case failed). |

## Report output formats

### JSON (`render_json_report`)

```json
{
  "run_id": "uuid4",
  "started_at": "2026-06-29T10:00:00Z",
  "finished_at": "2026-06-29T10:00:42Z",
  "git_sha": "0a0946f",
  "model_version": "deepseek-v4-pro",
  "environment": "CI",
  "total_cases": 12,
  "passed_cases": 10,
  "failed_cases": 2,
  "skipped_cases": 0,
  "aggregate_pass_rate": 0.833,
  "per_node": { "interview.score": { "passed": 4, "failed": 1 } },
  "case_results": [
    {
      "case_id": "interview-score-001",
      "node": "interview.score",
      "status": "failed",
      "trace_id": "abc123...32hex",
      "run_id": "run-001",
      "artifact_ref": "unavailable",
      "langsmith_url": "unavailable"
    }
  ]
}
```

US7 T125: trace_id / artifact_ref / langsmith_url are **top-level** per-case
keys (also preserved under `metrics.trace_id` for back-compat). Missing
values render as the literal string `"unavailable"` (never `null`,
never empty, never `"unknown"`).

### Markdown (`render_markdown_report`)

Six sections, in order:

1. **Header** — run_id, branch, git_sha, model, environment, started_at/finished_at.
2. **Summary** — total / passed / failed / skipped + aggregate pass rate.
3. **Per-case verdicts** — table with `Case ID | Node | Status | Latency (ms) | Cost (USD)`.
4. **Debug identifiers** — trace_id, artifact_ref, langsmith_url per case (LangSmith = `"unavailable"` while US6 is deferred).
5. **Failed-case drilldown** — table with `Case ID | Trace | Run | Artifact | LangSmith` for failed cases only. Section header + table format unchanged from US5.
6. **Aggregate stats** — per-node pass/fail/skip counts.

When there are zero failed cases, section 5 renders as
`No failing cases.` (graceful, not blank).

## Override workflow (FR-024)

The `override-record` subcommand enforces the dual-approval policy:

- **Both** `--pm-approver` and `--technical-approver` are required (the
  CLI hard-fails with exit 3 if either is missing).
- `--reason` is required (max 2000 characters).
- `--evidence` is validated:
  - `http(s)://` URLs: rejects loopback / private / link-local hosts
    (no exfiltration of override records to internal admin pages).
  - `file://` URLs and absolute paths: accepted as-is (CI runners
    reference `/var/log/...` legitimately).
  - Bare relative paths: rejects `..` segments (path-traversal guard).
  - Other schemes: rejected (`ftp://`, `javascript:`, etc.).
- Records accumulate in process memory (`_OVERRIDE_RECORDS`, soft cap
  1000) and are forwarded to an optional persistence sink
  (`set_override_record_sink`) — US8 badcases integration wires this to
  the `override_records` DB table.

The override record shape:

```json
{
  "overrideId": "override-<uuid4>",
  "runId": "<eval run id>",
  "gate": "pr_eval | baseline_refresh | emergency_override",
  "pmApprover": "alice@intercraft.io",
  "technicalApprover": "bob@intercraft.io",
  "reason": "...",
  "evidenceRef": "...",
  "timestamp": "2026-06-29T10:00:42Z"
}
```

## Programmatic usage

```python
from app.eval.runner import EvalRunner, EvalReport
from app.eval.report import render_json_report, render_markdown_report

runner = EvalRunner(
    cases=golden_cases,
    mode="mock",
    model_name="mock-llm",
    environment="CI",
    branch="master",
)
report: EvalReport = asyncio.run(runner.run_all())

# JSON (stable across runs, CI-friendly)
json_payload = render_json_report(report)
Path("report.json").write_text(json.dumps(json_payload, indent=2))

# Markdown (human-readable, 6 sections)
md = render_markdown_report(report)
Path("report.md").write_text(md)
```

## Tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/eval/test_033_eval_report_renderer.py` | 13 | JSON shape + Markdown sections + back-compat legacy dict input |
| `tests/eval/test_033_eval_cli_contract.py` | 13 | CLI exit codes 0/1/2/3/4 + override-record validation (loopback reject, path traversal, missing dual approval) |
| `tests/eval/test_033_failed_case_trace_links.py` | 13 | Per-case `trace_id` / `run_id` / `case_id` / `artifact_ref` surfaced |
| `tests/eval/test_033_trace_unavailable.py` | 9 | `"unavailable"` defaulting when trace/run/langsmith missing |
| `tests/eval/test_033_nightly_real_model_with_zero_budget_returns_incomplete.py` | 1 | Budget check + INCOMPLETE status (pre-existing, see follow-ups) |

## Follow-ups

- The 033-POLISH restoration items (`app/modules/telemetry_contracts/
  {events,redaction,retention}.py`, `app/agents/interview/
  planner_graph.py`) are tracked separately and do not block this
  module — the lazy-import pattern in `__init__.py` keeps the public
  surface importable.
- US6 (LangSmith sync) is deferred; `langsmith_url` defaults to
  `"unavailable"` in every report path until the SDK is installed.
- US8 will wire `set_override_record_sink` to the `override_records`
  DB table so records survive process restart.

## REQ-045 LLM Ops eval workflow

REQ-045 promotes this package from a local eval/report renderer into the
canonical LLM Ops automation surface:

- `python -m app.eval.cli run` remains the blocking local verdict source for CI.
- LangSmith sync is optional and auxiliary; it may add dataset, experiment,
  feedback, and deep-link context, but it must not decide pass/fail status.
- Planned commands extend this module with `langsmith-sync`, `export-audit`,
  `judge-run`, `judge-calibrate`, `experiment-compare`, and prompt proposal
  workflows.
- Every report must keep stable local JSON and Markdown artifacts even when
  LangSmith is disabled or unavailable.
- Production LangSmith export may include full AI prompt/output content only
  after the destination policy authorizes it. Operational secrets are forbidden
  in every destination.

The feature spec, contracts, and validation checklist live under
`specs/045-llm-ops-eval-workflow/`.

### REQ-045 examples

LangSmith disabled/local canonical mode:

```bash
uv run python -m app.eval.cli run \
  --suite golden \
  --env ci \
  --report-out docs/evidence/045-llm-ops-eval-workflow/run/eval-report.json \
  --markdown-out docs/evidence/045-llm-ops-eval-workflow/run/eval-report.md \
  --sync-langsmith never \
  --json
```

LangSmith required mode:

```bash
uv run python -m app.eval.cli run \
  --suite golden \
  --env ci \
  --report-out docs/evidence/045-llm-ops-eval-workflow/run/eval-report.json \
  --markdown-out docs/evidence/045-llm-ops-eval-workflow/run/eval-report.md \
  --sync-langsmith require \
  --json
```

Sync an existing local report:

```bash
uv run python -m app.eval.cli langsmith-sync \
  --report docs/evidence/045-llm-ops-eval-workflow/run/eval-report.json \
  --project intercraft-production \
  --destination-policy production-langsmith-full-content-v1 \
  --json
```

## REQ-061 投影 / 隐私

- `project_runtime_event`：策略授权的 LangSmith 投影（metadata/redacted/restricted），不调用引擎。
- 生产导出必须带 export-policy decision；失败不得回写 runtime 事实。
- Runbook：投影 backlog 用 runtime CLI `projection-status` / `projection-retry` 追赶，禁止重跑 AI。
