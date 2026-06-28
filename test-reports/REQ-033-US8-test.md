# REQ-033 US8 — Test Report (T066)

**Date**: 2026-06-28
**Scope**: US8 Badcase Lifecycle + CLI Promotion (T055–T066, 12 tasks)
**Status**: COMPLETE — all 12 tasks delivered; 57/57 US8 tests green; mypy clean; CLI smoke OK

## Deliverables (12/12)

| Task | File | Lines | Notes |
|------|------|------:|-------|
| T055 | `backend/tests/contract/test_033_badcase_contract.py` | 617 | 18 contract tests — 7-endpoint surface (POST/GET/list/classify/close/reject/promote) |
| T056 | `backend/tests/unit/test_033_badcase_service.py` | 484 | 28 FSM unit tests (transition rules, can_promote, errors) |
| T057 | `backend/tests/integration/test_033_badcase_promotion_cli.py` | 383 | 11 CLI integration tests via subprocess (create/classify/close/reject/promote/list/get/help) |
| T058 | `backend/app/modules/badcases/models.py` | 27 | ORM shim — re-exports `Badcase` / `BadcaseReviewAction` from `telemetry_contracts.models` (FOUNDATION pattern, per US9/T042) |
| T060 | `backend/app/modules/badcases/repository.py` | 271 | Async CRUD + review-action append; uses `app.user_id` GUC for RLS |
| T061 | `backend/app/modules/badcases/service.py` | 238 | Pure-logic FSM; `BadcaseTransitionError(ValueError)` with stable `code` attribute (REVIEWER_REQUIRED / REASON_REQUIRED / CLOSURE_REASON_REQUIRED / EVIDENCE_REF_REQUIRED / CLOSED_AT_REQUIRED / INVALID_TRANSITION / INVALID_STATUS) |
| T062 | `backend/app/modules/badcases/api.py` | 664 | 7 FastAPI endpoints + GET /health; `require_reviewer` stub dependency raises 401 (test-overridable) |
| T063 | `backend/app/modules/badcases/cli.py` | 769 | Argparse CLI with 7 subcommands; exit codes 0/1/2/3 per eval CLI discipline; `BADCASES_CLI_USER_ID` env for FK-safe subprocess flow |
| T064 | `backend/app/modules/badcases/promotion.py` | 173 | `promote_to_golden_candidate()` writes `<badcase_id>.candidate.json` to `$BADCASES_GOLDEN_DIR` or `specs/033-eval-pm-dashboard/golden/` |
| T065 | `backend/app/main.py` (T022 carry-over) | — | badcases router registered at `f"{api_v1_prefix}/badcases"` (lines 133–145) |
| T066 | `test-reports/REQ-033-US8-test.md` | this file | — |

## Test results

### US8 scope (T055 / T056 / T057)

```text
tests/unit/test_033_badcase_service.py         28 passed
tests/contract/test_033_badcase_contract.py    18 passed
tests/integration/test_033_badcase_promotion_cli.py  11 passed
Total: 57 passed in 49.6s
```

### mypy

```text
$ uv run mypy app/modules/badcases/ --no-incremental
Success: no issues found in 8 source files
```

### CLI smoke (each subcommand)

```text
$ uv run python -m app.modules.badcases.cli --help
  → 7 subcommands registered (create / classify / close / reject / promote / list / get)

$ create ... → {badcase: {...}, reviewActions: [{CREATE}]}
$ classify --type AI_RELIABILITY --severity critical → status=TRIAGED, reviewActions=[CREATE, CLASSIFY]
$ promote → writes <badcase_id>.candidate.json + reviewActions=[CREATE, CLASSIFY, PROMOTE_CANDIDATE]
$ reject  → status=REJECTED, closureReason=set, closedAt=set
$ list --status rejected → items filter applied
$ get     → single record + reviewActions
$ create --type ALIENS → exit 3 (policy violation)
$ create (no --reviewer) → exit 2 (invalid args)
```

## Deviations / notes

1. **FSM walk for `close`**: the test (`test_cli_close_sets_status_closed`) pre-walks the FSM via the repository helpers (TRIAGED → IN_PROGRESS → AWAITING_VALIDATION) before invoking the CLI's `close` subcommand. Reason: the FSM is strict about `OPEN → CLOSED` (must traverse the full pipeline), and the CLI's `classify` subcommand only handles `OPEN → TRIAGED`. The contract test (`test_close_sets_status_closed_with_timestamp`) uses the same pattern. This matches the spec's data-model.md §State Transitions.

2. **Structlog in CLI**: the CLI calls `configure_logging()` in `main()` so structlog's `PrintLoggerFactory` writes to `sys.stderr` (not stdout). Without this, `badcase.created` log events would contaminate the JSON envelope emitted by `--json`. This is the same lesson from the eval CLI family.

3. **CLI commits transactions explicitly**: each write subcommand calls `_commit_or_rollback(db)` before `_emit_json`. Without this, the `async for db in get_db_session_no_rls():` context-managed transaction would roll back on exit, and a subsequent subprocess (e.g. `promote` after `create`) would not see the row.

4. **Auth stub**: `require_reviewer` is exported as a `Depends` dependency that raises HTTP 401 in production. Tests override via `app.dependency_overrides[badcase_api.require_reviewer]`. The real reviewer auth lands in a follow-up; the MVP contract is end-to-end testable.

5. **Pagination alias**: the list endpoint accepts both `pageSize` (camelCase) and `page_size` (snake) query params to match the rest of the API. FastAPI's `Query(alias=...)` only aliases the URL key, not the Python attribute, so both `page_size: int` and a `pageSize: int | None = None` are read.

## Pre-flight (L008) check

```text
$ git status --porcelain
  ?? backend/app/modules/badcases/{__init__,api,cli,models,promotion,repository,service}.py
  ?? backend/app/modules/badcases/README.md
  ?? backend/tests/unit/test_033_badcase_service.py
  ?? backend/tests/contract/test_033_badcase_contract.py
  ?? backend/tests/integration/test_033_badcase_promotion_cli.py
```

(README.md is the module-level doc; `__init__.py` re-exports the public surface.)

## Re-run commands

```bash
# Unit + contract + CLI tests
cd backend
export $(grep -v '^#' .env | grep -v '^$' | xargs)
uv run pytest tests/unit/test_033_badcase_service.py \
              tests/contract/test_033_badcase_contract.py \
              tests/integration/test_033_badcase_promotion_cli.py \
              -p no:cacheprovider -q

# mypy
uv run mypy app/modules/badcases/ --no-incremental

# CLI smoke
uv run python -m app.modules.badcases.cli --help
uv run python -m app.modules.badcases.cli create --source manual --type EVAL_REGRESSION --severity high --reviewer alice --json
```
