# `app.modules.telemetry_contracts` — Event / metric / redaction / retention contracts (REQ-033 US9 / US10 / US7)

Self-contained library that defines the canonical contracts for
telemetry data flowing through PM Dashboard, eval reports, and
badcase audit logs. Has **no** runtime dependency on LangSmith, OTel,
FastAPI, SQLAlchemy, or DB — pure-Python dataclasses + stdlib.

> **033-POLISH restoration note**: `events.py`, `redaction.py`,
> `retention.py`, and `models.py` are planned 033 modules that are
> not yet present in the working tree. The `__init__.py` exposes lazy
> / tolerant imports so the public surface remains importable even
> when those files are absent. The CLI wrappers
> (`redaction_cli.py`, `retention_cli.py`) and `costs.py` +
> `metrics.py` + `repository.py` + `schemas.py` are committed and
> fully functional. Restore the missing files in the 033-POLISH
> follow-up to re-export the full public surface.

## Public surface (current — what loads cleanly today)

| Symbol | Source | Purpose |
|--------|--------|---------|
| `MetricDefinition` | `metrics.py` | Contract for one metric snapshot row. Frozen dataclass. |
| `MetricCatalog` | `metrics.py` | In-memory registry of `MetricDefinition` rows. |
| `Aggregation` | `metrics.py` | `Literal["sum", "avg", "p50", "p95", "p99"]` type alias. |
| `build_default_catalog()` | `metrics.py` | Pre-registers 6 built-in PM Dashboard V1 Overview metrics. |
| `estimate_cost(prompt, completion, model)` | `costs.py` | Pure USD cost calculator. Used by LLM client + PM Dashboard. |
| `MODEL_RATES` | `costs.py` | Per-1k-token USD rate table for gpt-4o / gpt-4o-mini / deepseek-chat / deepseek-coder / mock. |
| `TraceRunRef` | `repository.py` | 4-field dataclass: `case_id` / `trace_id` / `run_id` / `langsmith_url`. All `Optional`. |
| `build_trace_run_ref(...)` | `repository.py` | Constructor that accepts an `AIInvocationRecord` ORM / dict / None. |
| `extract_trace_id_from_ai_invocation(record)` | `repository.py` | Reads `trace_id` column from ORM / dict / None; returns `None` when missing. |
| `lookup_run_metadata(record)` | `repository.py` | Returns the parent eval run id from `AIInvocationRecord.run_id`; returns `None` when absent. |
| `trace_id_for_display(t)` / `run_id_for_display(r)` / `langsmith_url_for_display(u)` | `repository.py` | Map `None` / `""` / `"unknown"` → literal `"unavailable"` per US7 T123. |
| `TRACE_UNAVAILABLE` | `repository.py` | Canonical `"unavailable"` sentinel. |
| `VersionContext` / `ENVIRONMENTS` / `RELEASE_STAGES` / `AI_INVOCATION_STATUSES` | `schemas.py` | Pydantic v2 enums + version-context model. |
| `AIInvocationSummaryV2` | `schemas.py` | Pydantic v2 model for AI invocation summary (V2 supersedes the dataclass form). |

## Public surface (planned — restored in 033-POLISH)

These symbols are part of the contract surface and will be restored
from the README:

| Symbol | Purpose |
|--------|---------|
| `ProductEvent` / `AIInvocationSummary` / `MetricSnapshot` (dataclass form) | Streaming-event pipeline contracts (FR-019 / FR-020). |
| `dict_to_event` / `event_to_dict` | JSON-safe round-trip helpers. |
| `RedactionPolicy` (enum) / `RedactionContext` / `RedactionAudit` | Redaction pipeline contracts (FR-030–FR-032). |
| `apply_redaction` / `audit_redaction` / `validate_redaction` | Redaction helpers. |
| `production_default_context` / `staging_default_context` / `dev_default_context` | Env-specific default contexts. |
| `PII_FIELDS` / `METADATA_FIELDS` / `VALID_ENVIRONMENTS` | Field / env whitelists. |
| `RetentionContext` / `RetentionAction` / `enforce_retention` / `next_cleanup_at` | Retention contract + helpers (FR-035). |
| `Badcase` / `BadcaseReviewAction` (ORM, in `models.py`) | Badcase tables; `badcases/models.py` re-exports via lazy import. |

## Events (planned dataclass shape — restore from this README)

`ProductEvent` is the canonical event flowing through the eval +
telemetry pipeline:

```python
from app.modules.telemetry_contracts import ProductEvent, event_to_dict

event = ProductEvent(
    event_name="auth.registered",
    user_id="uuid",
    occurred_at="2026-06-29T10:00:00Z",
    properties={"environment": "production"},
    version_context=VersionContext(
        app_version="0.4.0",
        prompt_fingerprint="sha256:abc...",
        model="deepseek-v4-pro",
        rubric_version="v3",
        experiment_id=None,
    ),
)
json_payload = event_to_dict(event)
# Round-trip via dict_to_event(json_payload)
```

## Metrics (6 built-in PM Dashboard V1 Overview metrics)

```python
from app.modules.telemetry_contracts import build_default_catalog

catalog = build_default_catalog()
# catalog.list() -> list[MetricDefinition]
# catalog.get("active_users_30d") -> MetricDefinition
```

The 6 built-in metrics:

| `metric_id` | Aggregation | Source event |
|-------------|-------------|--------------|
| `registered_users_30d` | `sum` | `auth.registered` |
| `active_users_30d` | `sum` | `user.active` |
| `completed_ai_tasks_30d` | `sum` | `ai.call_completed` |
| `ai_success_rate_30d` | `avg` | `ai.call_completed` |
| `total_tokens_30d` | `sum` | `ai.call_completed` |
| `open_badcases` | `sum` | `badcase.created` (minus closed) |

Sub-batches 2+ add US2 / US3 / US4 / US7 specific metric definitions.

## Cost calculator (the canonical USD estimator)

```python
from app.modules.telemetry_contracts import estimate_cost

# 1000 prompt + 500 completion on gpt-4o-mini
cost = estimate_cost(1000, 500, "gpt-4o-mini")
# = 0.00015 + 0.0006 * 0.5 = 0.00045 USD

# Mock model → zero cost (test pipeline)
assert estimate_cost(1000, 500, "mock") == 0.0

# Unknown model → fallback rate ($0.001 / $0.002 per 1k)
cost = estimate_cost(1000, 500, "future-model")

# Negative tokens clamp to 0
assert estimate_cost(-100, 500, "gpt-4o") >= 0.0
```

The PM Dashboard AI Operations panel reports `estimated_cost` via
this function — the contract is `estimate_cost(prompt, completion,
model) == summary.estimated_cost` for matching inputs, so a single
function powers both the LLM client write path and the dashboard
read path.

## Redaction (FR-030–FR-032, US10)

The redaction pipeline gates every external export. The contract:

- **Production** — PII fields are mandatory-redacted; missing
  `audit_redaction` → policy violation → export refused.
- **Staging** — PII fields recommended-redacted; missing audit →
  warning + export allowed.
- **Dev / CI** — no-op (development convenience).

```python
from app.modules.telemetry_contracts import (
    apply_redaction, audit_redaction, validate_redaction,
    production_default_context,
)

ctx = production_default_context()
redacted = apply_redaction(payload, ctx)
audit = audit_redaction(payload, redacted, environment="production")
validate_redaction(redacted, environment="production")
```

CLI for the redaction audit:

```bash
python -m app.modules.telemetry_contracts.redaction audit \
    --environment production \
    --sample docs/evidence/run-001/export-sample.json \
    --out docs/evidence/run-001/redaction-check.md \
    --json
```

Exit codes: 0 (all passed) / 1 (operational) / 2 (invalid args) /
3 (policy violation — forbidden production content detected).

## Retention (FR-035a)

Env-specific defaults:

| Environment | Action | Window |
|-------------|--------|--------|
| `production` | `delete` | 30 days |
| `staging` | `archive` | 7 days |
| `dev` / `ci` | no-op | — |

```python
from app.modules.telemetry_contracts import (
    enforce_retention, next_cleanup_at,
    production_default_context,
)

ctx = production_default_context()
report = enforce_retention(expired_rows, ctx)
# report["action"] = "delete"
# report["expired_count"] = int
```

CLI:

```bash
python -m app.modules.telemetry_contracts.retention check \
    --environment production \
    --json
```

Production runs are always dry-run (operator-triggered deletion only).

## TraceRunRef (US7 T126 — fully shipped)

```python
from app.modules.telemetry_contracts import (
    build_trace_run_ref, trace_id_for_display,
)

ref = build_trace_run_ref(
    record=ai_invocation_row,         # ORM / dict / None
    case_id="interview-score-001",    # eval case id
)
# ref.trace_id    -> "abc...32hex" or None
# ref.run_id      -> "run-001" or None
# ref.langsmith_url -> None (US6 deferred)

# Render: None → "unavailable"
display = trace_id_for_display(ref.trace_id)
# = "unavailable" if ref.trace_id is None else ref.trace_id
```

The same contract is used by `eval/report.py` (per-case trace column
in the JSON + Markdown drilldown) and by `badcases/service.py`
(`promote_with_trace_evidence`).

## Programmatic usage — quick reference

```python
# Cost estimation
from app.modules.telemetry_contracts import estimate_cost

# Catalog lookup
from app.modules.telemetry_contracts import build_default_catalog
catalog = build_default_catalog()

# Trace/run display
from app.modules.telemetry_contracts import (
    build_trace_run_ref, trace_id_for_display, run_id_for_display,
)

# Version context (Pydantic v2)
from app.modules.telemetry_contracts import VersionContext, ENVIRONMENTS
```

## Tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_033_ai_cost_estimates.py` | 14 | `estimate_cost` per-model rates, fallback, negative clamping |
| `tests/eval/test_033_failed_case_trace_links.py` | 13 | `TraceRunRef` surfacing in JSON + Markdown |
| `tests/eval/test_033_trace_unavailable.py` | 9 | `"unavailable"` defaulting when trace/run/langsmith missing |
| `tests/contract/test_033_pm_dashboard_contract.py` | 9 | PanelResponse envelope (uses `VersionContext`) |
| `tests/contract/test_033_telemetry_contracts.py` | TBD | Restore alongside `events.py` / `redaction.py` / `retention.py` |

## Follow-ups (033-POLISH restoration)

The following source files are part of the locked contract but are
not in the working tree. The `__init__.py` exposes them via lazy /
tolerant imports so callers don't crash; restore the source files
in the 033-POLISH batch:

- `app/modules/telemetry_contracts/events.py` (ProductEvent /
  AIInvocationSummary / MetricSnapshot dataclasses + JSON round-trip)
- `app/modules/telemetry_contracts/redaction.py`
- `app/modules/telemetry_contracts/retention.py`
- `app/modules/telemetry_contracts/models.py` (SQLAlchemy ORM
  consolidated in FOUNDATION; `badcases/models.py` re-exports
  `Badcase` + `BadcaseReviewAction` from here)

The CLI wrappers (`redaction_cli.py` / `retention_cli.py`) work
today — they import from the planned modules via lazy import paths
and degrade to in-memory stand-ins when the source files are absent.
The contract (exit codes, JSON shape, dry-run flag) is fixed by
those CLI modules regardless of whether the source modules are
restored.
