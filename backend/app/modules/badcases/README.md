# `app.modules.badcases` — Badcase review workflow (REQ-033 US8)

Badcase lifecycle FSM, reviewer audit log, and promotion-to-golden-candidate
workflow. Owns the `badcases` + `badcase_review_actions` tables and
the canonical 7-endpoint FastAPI router.

## State machine

```
OPEN ──▶ TRIAGED ──▶ IN_PROGRESS ──▶ AWAITING_VALIDATION ──▶ CLOSED
  │         │                              │
  │         └──────────────────────────────┴──▶ AWAITING_VALIDATION (re-open)
  │
  └────────────────▶ REJECTED
TRIAGED ──▶ REJECTED
```

`CLOSED` and `REJECTED` are terminal — no transitions out.

### Required fields per target status

| Target status | Required fields |
|---------------|-----------------|
| `OPEN` | (none — initial status) |
| `TRIAGED` | `reviewer` |
| `IN_PROGRESS` | `reviewer` |
| `AWAITING_VALIDATION` | `reviewer` |
| `CLOSED` | `closure_reason` + `evidence_ref` + `reviewer` + `closed_at` (FR-029) |
| `REJECTED` | `reason` + `reviewer` + `closed_at` (FR-029) |

### FSM error codes

`BadcaseTransitionError.code` — stable codes the API layer maps to
HTTP 422:

| Code | When |
|------|------|
| `REVIEWER_REQUIRED` | `reviewer` missing for any non-OPEN target |
| `REASON_REQUIRED` | `reason` missing for `REJECTED` |
| `CLOSURE_REASON_REQUIRED` | missing for `CLOSED` |
| `EVIDENCE_REF_REQUIRED` | missing for `CLOSED` |
| `CLOSED_AT_REQUIRED` | missing for `CLOSED` / `REJECTED` |
| `INVALID_TRANSITION` | terminal state or pipeline bypass |
| `INVALID_STATUS` | unknown target status |

## API endpoints

Mounted at `/api/v1/badcases` (prefix set in `backend/app/main.py`).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/badcases` | Create a new badcase |
| `GET` | `/api/v1/badcases` | List (filter by status / type / severity) |
| `GET` | `/api/v1/badcases/{id}` | Read one |
| `POST` | `/api/v1/badcases/{id}/classify` | Update type + severity, append `CLASSIFY` action |
| `POST` | `/api/v1/badcases/{id}/close` | Set `CLOSED` + `closure_reason` + `closed_at`, append `CLOSE` action |
| `POST` | `/api/v1/badcases/{id}/reject` | Set `REJECTED` + `reason`, append `REJECT` action |
| `POST` | `/api/v1/badcases/{id}/promote` | Write candidate file + append `PROMOTE_CANDIDATE` action |
| `GET` | `/health` | Liveness (T022 placeholder) |

`require_reviewer` is a stub that raises 401 by default; tests
override via `app.dependency_overrides[require_reviewer] = ...`. RLS
is pre-set per request via `_db_session_with_rls(user_id)`.

## CLI subcommands

`python -m app.modules.badcases.cli` exposes the same 7 operations as
the API:

```bash
# Create
python -m app.modules.badcases.cli create \
    --source eval_failure --type EVAL_REGRESSION \
    --severity high --reviewer alice --json

# Classify (re-prioritize)
python -m app.modules.badcases.cli classify \
    --badcase-id badcase-... --type USER_REPORT \
    --severity medium --reviewer alice --json

# Close (with closure reason + evidence link)
python -m app.modules.badcases.cli close \
    --badcase-id badcase-... --reviewer alice \
    --closure-reason "fixed in commit 0a0946f" \
    --evidence-ref "https://github.com/intercraft/intercraft/pull/123" --json

# Reject
python -m app.modules.badcases.cli reject \
    --badcase-id badcase-... --reviewer alice \
    --reason "out of scope for V1" --json

# Promote (writes specs/033-*/golden/<id>.candidate.json)
python -m app.modules.badcases.cli promote \
    --badcase-id badcase-... --reviewer alice \
    --redaction-audit-id audit-001 \
    --reason "protect against regression" --json

# List
python -m app.modules.badcases.cli list --status OPEN --page 1 --page-size 20 --json

# Get one
python -m app.modules.badcases.cli get --badcase-id badcase-... --json
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Operational failure (DB error, IO error, not-found) |
| 2 | Invalid args |
| 3 | Policy violation (FSM rejection, e.g. unknown type, redaction not passed) |

## Promotion to golden candidate (FR-022)

When a closed badcase should become a regression test, the reviewer
runs `promote`:

1. The badcase's evidence is re-redacted via
   `apply_redaction(environment=production)` and the result is
   fingerprinted (SHA-256 over the canonical JSON form).
2. A candidate file is written to `specs/<spec-dir>/golden/<id>.candidate.json`
   with the redacted evidence + the new expected rubric.
3. A `PROMOTE_CANDIDATE` action is appended to
   `badcase_review_actions` with the redaction audit id + reason.
4. The candidate sits in the spec dir until a reviewer promotes it
   to `golden/*.json` (separate workflow — `badcase_promote_to_golden.py`).

US9 wires the eval runner to consume both `golden/*.json` (active)
and `golden/*.candidate.json` (pending review).

## Trace evidence linking (US7 T128)

`service.promote_with_trace_evidence(badcase, ...)` is the convenience
wrapper for closing a badcase with automatic trace capture:

```python
from app.modules.badcases import service

closed = service.promote_with_trace_evidence(
    badcase,
    reviewer="alice",
    closure_reason="fixed in commit 0a0946f",
    evidence_ref="https://github.com/.../pull/123",
)
# When auto_capture_trace=True (default) and no evidence_ref is supplied,
# the active OTel trace id is captured and prepended as
# `trace:<id>` so the badcase row links back to the originating trace.
# When no trace is active, `trace:unavailable` is recorded — never silent
# omission, per US7 T123.
```

The function delegates the FSM transition to `service.transition()` so
all the existing rules (REVIEWER_REQUIRED / CLOSURE_REASON_REQUIRED /
EVIDENCE_REF_REQUIRED / etc.) still apply.

## Module map

| File | Purpose |
|------|---------|
| `models.py` | Re-exports `Badcase` + `BadcaseReviewAction` from `app.modules.telemetry_contracts.models` (033 FOUNDATION consolidated all 033 tables into one module). |
| `service.py` | Pure FSM: `transition(badcase, target_status, ...)` enforces all required-field rules. `promote_with_trace_evidence` adds trace-evidence enrichment. |
| `repository.py` | Async SQLAlchemy 2.0 helpers for `badcases` + `badcase_review_actions` (create / list / get / classify / close / reject / promote). |
| `schemas.py` | Pydantic v2 models: `Badcase`, `BadcaseReviewAction`, request/response shapes, `BADCASE_STATUSES` / `BADCASE_TYPES` / `BADCASE_SOURCES` / `BADCASE_SEVERITIES` enums. |
| `promotion.py` | `promote_to_golden_candidate(badcase, ...)` — re-redaction + SHA-256 fingerprint + candidate file write + audit log. |
| `api.py` | FastAPI router. 7 endpoints + `require_reviewer` stub + `_db_session_with_rls` dependency. |
| `cli.py` | `python -m app.modules.badcases.cli` — 7 subcommands + `--json` flag. |

## Tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_033_badcase_fsm.py` | 18 | FSM transition rules, required-field errors, terminal states |
| `tests/integration/test_033_badcase_review_actions.py` | 12 | Audit log append on every transition |
| `tests/integration/test_033_badcase_promotion.py` | 8 | Candidate file write + fingerprint determinism |
| `tests/contract/test_033_badcase_api_contract.py` | 9 | API endpoint shapes + 422 error envelope |

## Follow-ups

- Production `require_reviewer` resolver — replace the 401 stub once
  reviewer role mapping lands.
- US8 will wire `set_override_record_sink` (eval) to the
  `override_records` DB table (co-located in `badcases`) so override
  records survive process restart.
- The 033-POLISH restoration items
  (`app/modules/telemetry_contracts/{events,redaction,retention,models}.py`)
  are tracked separately. `badcases/models.py` re-exports via lazy
  import so the public surface is importable even when the source
  files are absent.

## REQ-061 运营面

- Canonical Bad Case facade：`/api/v1/admin-console/ai/badcases*`
- 与任务检查反向链接：`?task_id=` 可从运营任务详情跳转
- 隐私：默认脱敏；揭示需 reason/TTL + 审计
