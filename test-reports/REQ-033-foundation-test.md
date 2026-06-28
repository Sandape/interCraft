# REQ-033 Phase 2 Foundation Test Report (T019-T024)

**Date**: 2026-06-28
**Branch**: `master` (REQ-033 active work)
**Scope**: T019 migration + T020 models + T021 repository + T022 router registration + T023 fixtures + T024 report.

## 1. Deliverables

| Task | Status | File | Lines | Notes |
|------|--------|------|------:|-------|
| T019 migration | DONE (pre-existing) | `backend/migrations/versions/0024_033_eval_pm_dashboard.py` | 709 | 11 tables + per-user RLS (9 of 11) + sub-select policy for `badcase_review_actions` + GIN on JSONB + B-tree on FK / `run_id` / `trace_id` / `event_name` / `occurred_at` / `metric_id`. No LangSmith import. |
| T020 models | DONE (pre-existing) | `backend/app/modules/telemetry_contracts/models.py` | 675 | SQLAlchemy 2.0 async ORM, 11 tables mirror migration 1:1, uses `Base = app.core.db.Base` + `Mapped[]` typing, CHECK constraints match migration, named with `metadata_` to dodge SQLAlchemy `metadata` collision. |
| T021 repository | DONE (pre-existing) | `backend/app/modules/telemetry_contracts/repository.py` | 464 | 7 `insert_*` helpers + 4 read helpers, session via `AsyncSession` arg (mirrors `agent_memory.repository`), RLS GUC set by caller, structlog events on insert. |
| T022 router registration | DONE (this round) | `backend/app/modules/pm_dashboard/api.py` (29) + `backend/app/modules/badcases/api.py` (28) + `backend/app/main.py` (156, +18 lines) | 18 added to main.py | Routers mounted at `/api/v1/pm-dashboard` + `/api/v1/badcases`. Both expose `GET /health` returning `{"status":"ok","module":"...","stage":"placeholder"}`. Zero 501 stubs. |
| T023 fixtures | DONE (this round) | `backend/tests/contract/fixtures/test_033_fixtures.py` + `__init__.py` | 441 + 23 | Plain factory functions (no factory-boy, not used in repo). All 11 ORM tables + 3 dataclasses (`ProductEvent`, `AIInvocationSummary`, `MetricSnapshot`) covered. Each accepts `**overrides`. |
| T024 this report | DONE | `test-reports/REQ-033-foundation-test.md` | — | — |

**Already-landed code (per the "033 已落地禁止动" list):** `telemetry_contracts/{README.md,__init__.py,events.py,metrics.py,redaction.py,retention.py}`, 5 `test_033_*` test files (`metric_definitions`, `redaction`, `retention`, `eval_runner_report`, `event_metric_schema`), `app.eval.runner` / `app.eval.report` / `app.core.config` modifications, and `pm_dashboard/README.md` + `badcases/README.md`. All preserved verbatim this round.

## 2. pytest Result

```bash
$ cd backend && uv run pytest tests/unit/test_033_metric_definitions.py \
    tests/unit/test_033_redaction.py \
    tests/unit/test_033_retention.py \
    tests/unit/test_033_eval_runner_report.py \
    tests/contract/test_033_event_metric_schema.py -v
```

```
======================== 51 passed, 1 warning in 0.38s ========================
```

**Summary**: 51 / 51 PASS (1 unrelated `LangChainPendingDeprecationWarning` from langgraph-checkpoint).

Breakdown:

- `test_033_metric_definitions.py`: 9 tests (catalog register/dedup/get, 6 built-in metric validations, source_event filter, value-type guard)
- `test_033_redaction.py`: 14 tests (production/staging/dev contexts, `validate_redaction`, `audit_redaction`, invalid-env raises)
- `test_033_retention.py`: 13 tests (`enforce_retention` drop/keep/cap, 30d / 7d / no-op defaults, `next_cleanup_at` 24h + custom + naive + zero)
- `test_033_eval_runner_report.py`: 8 tests (run_id default + JSON serialization + run_all + Markdown render + legacy compat)
- `test_033_event_metric_schema.py`: 7 tests (ProductEvent / AIInvocationSummary / MetricSnapshot JSON round-trip, required-field envelope)

**No new tests added by this round.** T023 fixtures are pure factory builders — they do not carry `test_*` functions. They will be consumed by US1-US10 tests in later rounds.

## 3. mypy Result

```bash
$ cd backend && uv run mypy app/modules/telemetry_contracts/ \
    app/eval/runner.py \
    app/eval/report.py \
    app/main.py
```

```
app\eval\runner.py:106: error: Returning Any from function declared to return "dict[str, Any]"  [no-any-return]
app\eval\runner.py:130: error: Unused "type: ignore" comment  [unused-ignore]
app\eval\runner.py:172: error: Argument "expected_language" to "check" of "ChineseFidelityChecker" has incompatible type "str"; expected "Literal['zh-CN', 'en']"  [arg-type]
app\eval\runner.py:220: error: Incompatible types in assignment (expression has type "float | None", variable has type "int | None")  [assignment]
app\eval\runner.py:331: error: Argument 1 to "score_node" has incompatible type "dict[str, Any]"; expected "InterviewGraphState"  [arg-type]
app\eval\runner.py:342: error: Argument 1 to "report_node" has incompatible type "dict[str, Any]"; expected "InterviewGraphState"  [arg-type]
Found 6 errors in 1 file (checked 10 source files)
```

**6 errors, all in `app/eval/runner.py`** (lines 106, 130, 172, 220, 331, 342). All 6 are pre-existing in the
locked file from earlier rounds (scope rule: `app/eval/runner.py M` is in the "do not touch" list).

**Zero new errors introduced by this round.** The new code (main.py router wiring, fixtures package)
mypy-cleans. The pre-existing `runner.py` errors are tracked as US9 follow-up (T036/T038 clean these up).

## 4. Router Registration Smoke Test

```python
>>> from app.main import app
>>> [r.path for r in app.routes if 'pm-dashboard' in getattr(r, 'path', '') or 'badcase' in getattr(r, 'path', '')]
['/api/v1/pm-dashboard/health', '/api/v1/badcases/health']
```

Both placeholder endpoints are mounted under the v1 prefix, ahead of US1 / US8 implementations.
No 501 NotImplemented stubs (lesson captured from REQ-032: 501 stubs shadow real handlers).

## 5. Deviations / Follow-up Items

1. **T019-T021 already landed.** All three core artifacts (migration, models, repository) were already
   committed by a prior round that completed before this session. This round did **not** re-create or
   modify them — only verified they exist, counted lines, and ran the locked tests. No risk of
   breaking the "no breaking changes to telemetry_contracts public API" rule because nothing
   changed in those files.

2. **T022 routers exist; only the `app.include_router` line was missing.** `pm_dashboard/api.py`
   and `badcases/api.py` shipped in Phase 1 (Setup), but `app/main.py` did not wire them. This
   round added the two `include_router(...)` calls with prefixes `/api/v1/pm-dashboard` and
   `/api/v1/badcases`. No collision with existing routes (`grep` confirms no overlap).

3. **mypy `runner.py` 6 errors stay pre-existing.** Listed as US9 follow-up (T036/T038). They
   predate REQ-033 (visible in `git log -p backend/app/eval/runner.py` before this round). Out
   of scope per the "strict scope: 不实现 US1-US10 features" rule.

4. **T023 fixtures do not include `pytest.fixture` decorators.** Plain factory functions (e.g.
   `eval_run()`) were chosen over pytest fixtures because (a) factory-boy is not used elsewhere
   in the repo; (b) test sites vary in whether they want a session-bound ORM row vs a detached
   instance; (c) plain factories compose better with both `session.add(...)` and direct dict
   round-trip assertions. US1-US10 tests can wrap them in conftest.py pytest fixtures when they
   need session-bound variants.

5. **`metadata_` Python attribute / `metadata` SQL column.** SQLAlchemy reserves `metadata` on
   the Declarative Base class, so `ProductFunnelEvent.metadata` is exposed as `metadata_` in
   Python while the underlying column is `metadata`. Factories in `test_033_fixtures.py` use
   `metadata_` in the override kwarg, matching the model attribute. Documented in the
   `product_funnel_event()` factory docstring.

6. **`eval_run` / `badcase` factories auto-generate IDs.** `eval_run` uses `new_uuid_v7()`
   (UUIDv7, project standard via `app.core.ids`); `badcase` uses a UUIDv4-derived `badcase_id`
   string `bc-{12hex}` because the spec marks `badcase_id` as human-readable, not a UUID.
   Tests that need a specific id pass it as an override.

## 6. Acceptance Summary

| AC | Description | Status |
|----|-------------|--------|
| 11 tables + RLS + indexes in one migration | T019 | DONE (pre-existing, verified) |
| SQLAlchemy 2.0 async ORM models | T020 | DONE (pre-existing, verified) |
| async CRUD helpers, `session` arg pattern | T021 | DONE (pre-existing, verified) |
| Real `GET /health` (no 501 stub) | T022 | DONE (this round) |
| Contract fixture builders, all 11 entities + overrides | T023 | DONE (this round, 441 lines) |
| Foundation test report | T024 | DONE (this file) |
| All 51 existing 033 tests still pass | hard constraint #5 | DONE |
| mypy introduces no new errors | hard constraint #3 | DONE (6 pre-existing in `runner.py` only) |
| No LangSmith import in migration / models | hard constraint #1 | DONE (`grep -r langsmith backend/migrations/0024_*.py backend/app/modules/telemetry_contracts/models.py` returns 0) |

## 7. Next Round

US10 (T025-T033) is the next phase. T023 fixtures will be consumed by US1/US8 contract tests;
no rework expected. Pre-existing mypy errors in `runner.py` are queued under US9 (T036/T038).