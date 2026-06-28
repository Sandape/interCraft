# `app.modules.pm_dashboard` — PM Dashboard V1 (REQ-033 US1–US4 + US7)

Five V1 panels backed by the same `PanelResponse[T]` envelope, the
same `DashboardFilter` query params, and the same RLS-pre-set async DB
session dependency.

## Panels

| ID | US | Endpoint | Purpose |
|----|----|---------|---------|
| Overview | US1 | `GET /api/v1/pm-dashboard/metrics/overview` | 8 FR-002 metric cards (UV / registered / active / AI completed / AI success rate / total tokens / est cost / open badcases). Bundled into a single `OverviewPanelData`. |
| Funnel | US1 | `GET /api/v1/pm-dashboard/metrics/funnel` | 4-step funnel (registered → active_users → completed_ai_tasks → ai_success_rate) with per-step conversion + largest-drop-off highlight. |
| Resume Diagnosis | US2 | `GET /api/v1/pm-dashboard/metrics/resume-diagnosis` | Resume diagnose start / complete counts, branches touched, AI success rate scoped to resume diagnosis events. |
| Mock Interview | US3 | `GET /api/v1/pm-dashboard/metrics/mock-interview` | Mock interview start / complete counts, avg score distribution, AI success rate scoped to mock interview events. |
| AI Operations | US4 | `GET /api/v1/pm-dashboard/metrics/ai-operations` | 7 core metrics + 3 latency percentiles (P50/P95/P99) + 4 top-N breakdowns (model / graph / node / prompt_fingerprint). |
| Version & Experiment | US7 | `GET /api/v1/pm-dashboard/metrics/version-experiment` | 5 distinct counts + 2 top-5 breakdowns (version 4-way / experiment) + `trace_available` flag. |

US6 (LangSmith sync + deep-link panel) is **deferred** — see Follow-ups.

## Filter contract

Every panel endpoint accepts the same query params:

| Param | Required | Type | Default | Notes |
|-------|----------|------|---------|-------|
| `dateFrom` | yes | ISO 8601 date | — | Inverted range → 400 |
| `dateTo` | yes | ISO 8601 date | — | Inverted range → 400 |
| `environment` | no | `local \| ci \| staging \| production` | `production` | Filtered via `product_events.properties->>'environment'` |
| `releaseStage` | no | `DEVELOPMENT \| BETA \| GA` | — | — |
| `appVersion` | no | string | — | — |
| `promptFingerprint` | no | SHA-256 hex | — | — |
| `model` | no | `gpt-4o \| gpt-4o-mini \| deepseek-chat \| deepseek-coder \| mock` | — | — |
| `rubricVersion` | no | string | — | — |
| `experimentId` | no | string | — | US7 only (defaults to `"unknown"` bucket when null) |
| `userId` | no | UUID | caller's UUID | RLS-protected; super-PM only |

`DashboardFilter` runs Pydantic `model_validator` (date_to > date_from)
and raises `ValueError` on bad input → the API maps to 400.

## Empty-window contract (SC-009)

All panels return **200 with empty-state body**, not 404, when the date
range contains zero events:

- `quality_flags.partial_data = True`
- `freshness_at = "unknown"`
- All count fields = 0
- Top-N breakdowns = `[]`
- Cost labeled `is_estimate = True` (FR-008)

The contract tests pin this explicitly (US1 scenario 3).

## RLS

Every request sets `app.user_id` via `SET LOCAL` before any query, so
`product_events` / `badcases` rows are scoped to the calling user. The
DB session dependency is `_db_session_with_rls(user_id: UUID = Depends(require_pm))`
— wraps `get_db_session_no_rls()` and explicitly calls `set_rls_user_id(session, user_id)`.

`require_pm` is a stub that raises 401 by default; tests override via
`app.dependency_overrides[require_pm] = ...`. Production resolver
(role mapping → user_id) is a follow-up US.

## ProductEvent fallback

When the canonical `ProductEvent` row is missing (e.g. backend telemetry
down, ARQ worker offline), the panels fall back to aggregating from
`ai_invocation_records` (the table populated by the LLM client hook in
US9 T040). The fallback is automatic and surfaces via:

- `source_of_truth = "product_events (grouped by ...)"` (label is
  consistent across panels even when the fallback path is taken).
- `missing_version_fields` populated with any null/unknown version
  dimensions (app_version, prompt_fingerprint, model, rubric_version).

This guarantees the dashboard never returns a blank card on
telemetry gaps.

## Privacy invariant (FR-008 / US10)

Panels **never** read or surface raw AI content. The privacy invariant
is enforced at three layers:

1. **Repository helpers** only read scalar columns (`status`,
   `retry_count`, `latency_ms`, `model`, `graph`, `node`,
   `prompt_fingerprint`, `prompt_tokens`, `completion_tokens`,
   `estimated_cost`, `created_at`). Never `prompt_text`,
   `completion_text`, `system_prompt`, `messages`, `tool_calls`,
   `request_body`, `response_body`, `raw_response`.
2. **Pydantic schemas** use `extra="forbid"` so any accidental
   raw-content field is rejected at validation.
3. **Integration tests** enumerate the 10 forbidden field names and
   assert they never appear in a panel payload. The frontend test
   scans all rendered `data-testid` attributes for raw-content
   substrings — catches future-component regressions.

## Module map

| File | Purpose |
|------|---------|
| `api.py` | FastAPI router. 6 metrics endpoints + `GET /health` placeholder. `_parse_filters` shared mapper, `_db_session_with_rls` shared dependency. |
| `service.py` | Pure orchestration. `get_overview` / `get_funnel` / `get_resume_diagnosis` / `get_mock_interview` / `get_ai_operations` / `get_version_experiment` + `validate_filters`. |
| `repository.py` | Async SQLAlchemy 2.0 helpers. 30+ functions across the 6 panels (counts, sums, percentiles, top-N breakdowns). All reuse existing tables — no new tables, no migrations. |
| `schemas.py` | Pydantic v2 models: `DashboardFilter`, `PanelResponse[T]`, the 6 `*PanelData` payloads, `QualityFlags`, `VersionBreakdownEntry`, `ExperimentBreakdownEntry`. All count fields `Field(ge=0)`, rate fields `Field(ge=0, le=1)`, `extra="forbid"`. |

## Programmatic usage

```python
from app.modules.pm_dashboard import service
from app.modules.pm_dashboard.schemas import DashboardFilter

filters = DashboardFilter(
    date_range_start="2026-06-01",
    date_range_end="2026-06-30",
    environment="production",
)

panels = await service.get_overview(session, filters)
# panels: list[PanelResponse[OverviewPanelData]]
# panels[0].data.ai_completed  # int
# panels[0].data.success_rate  # float (clamped [0, 1])
# panels[0].quality_flags.partial_data  # bool
# panels[0].freshness_at  # "unknown" or ISO 8601
```

## Tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/contract/test_033_pm_dashboard_contract.py` | 9 | Filter parsing 400/422, envelope shape, empty-state quality flags, funnel step coverage |
| `tests/integration/test_033_pm_dashboard_metrics.py` | 14 | Repository helper correctness, service assembly, FR-002 field coverage, cost estimate label, version-field "unknown" surfacing, empty-window flag |
| `tests/integration/test_033_resume_diagnosis_metrics.py` | 14 | US2 panel — diagnose counts + branch coverage |
| `tests/integration/test_033_mock_interview_metrics.py` | 14 | US3 panel — interview counts + score distribution |
| `tests/integration/test_033_ai_operations_metrics.py` | 17 | US4 panel — 9 repository helpers + 19-field payload + privacy assertion + rate clamping |
| `tests/integration/test_033_version_experiment_metrics.py` | 12 | US7 panel — 5 aggregates + 2 top-5 breakdowns + trace_available |
| `src/pages/__tests__/PMDashboard.test.tsx` | 4 | Page shell renders all 6 panels, loading skeleton, error state, date filter refetch |
| `src/components/pm-dashboard/__tests__/OverviewPanel.test.tsx` | 6 | 8 metric cards + quality flag + cost label |
| `src/components/pm-dashboard/__tests__/FunnelPanel.test.tsx` | 5 | 4 funnel steps + largest-drop-off highlight |
| `src/components/pm-dashboard/__tests__/ResumeDiagnosisPanel.test.tsx` | 7 | US2 panel rendering |
| `src/components/pm-dashboard/__tests__/MockInterviewPanel.test.tsx` | 6 | US3 panel rendering |
| `src/components/pm-dashboard/__tests__/AIOperationsPanel.test.tsx` | 12 | US4 panel — 8 cards + 4 breakdowns + privacy invariant |
| `src/components/pm-dashboard/__tests__/VersionExperimentPanel.test.tsx` | 10 | US7 panel — 5 cards + 2 tables + trace-unavailable badge |

## Follow-ups

- US6 (LangSmith deep-link panel) is **deferred** — `langsmith_url` is
  hard-coded to `"unavailable"` in every contract path until the SDK
  is installed. Flipping it on is a one-line change in
  `extract_trace_id_from_ai_invocation` + `build_trace_run_ref` once
  the SDK lands.
- Production `require_pm` resolver — replace the 401 stub once PM role
  mapping is in place. The 6 stub endpoints all accept the dependency
  override pattern, so wiring is local.
- The dashboard routes are mounted under `/api/v1/pm-dashboard/` per
  the README contract; the metrics endpoints live at
  `/api/v1/pm-dashboard/metrics/{overview,funnel,resume-diagnosis,
  mock-interview,ai-operations,version-experiment}`.
- Frontend page lives at `src/pages/PMDashboard.tsx`, route at
  `/pm-dashboard`, sidebar entry under 工具 (secondary nav).
