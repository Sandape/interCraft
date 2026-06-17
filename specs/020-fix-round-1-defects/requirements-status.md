# 020 Requirement Status

This file tracks the 12 requirement rows of feature 020 (`specs/020-fix-round-1-defects`).
A row is `done` only when the implementation change and the verification
evidence are both present. Until both exist, the row stays at the status
shown in `tasks.md` (initially `planned` for all 12).

## Fix Requirements

| Requirement | Summary | Defect | Priority | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| FIX-001 | `CreateErrorQuestionInput` accepts `source_session_id` and `source_question_id` on POST | D-002 | P0 | planned | pending | T1 |
| FIX-002 | Mount `JobsDetailPanel` into `src/pages/Jobs.tsx` (row onClick + conditional render) | D-014 | P1 | planned | pending | T2 — unblocks 5 round-1 cases |
| FIX-003 | `clear-source` is idempotent: second call returns 400 `source_already_cleared` | D-013 | P1 | planned | pending | T3 |
| FIX-004 | `clear-source` uses `PATCH` and the doc is updated | D-003 | P1 | planned | pending | T4 |
| FIX-005 | `?source=` is canonical; `?filter[source]=` is a deprecated alias | D-004 | P1 | planned | pending | T5 |
| FIX-006 | `POST /resume-branches` path is the source of truth; contracts updated | D-005 | P1 | planned | pending | T6 — doc-only |
| FIX-007 | `POST /interview-sessions` returns a Pydantic-validated response | D-006 | P1 | planned | pending | T7 |
| FIX-008 | `ErrorBook.tsx` list shows source filter UI and per-row source badge | D-009 | P2 | planned | pending | T8 |
| FIX-009 | `src/router.tsx` adds an auth guard for protected routes | D-016 | P2 | planned | pending | T9 |
| FIX-010 | `headcount` input has `type="number"` + `min={1}` + `step={1}` | D-017 | P2 | planned | pending | T10 |
| FIX-011 | Phase 4 Mock LLM is wired into `InterviewLive` for deterministic E2E | D-008 | P2 | planned | pending | T11 |
| FIX-012 | New E2E covers 100/101-char `salary_range_text` boundary | D-010 | P3 | planned | pending | T12 |

## Acceptance Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| AC-1 | All 12 active defects are closed | planned | pending | tasks.md "Final Verification" |
| AC-2 | Round-1 43 E2E cases rerun 43 passed / 0 failed / 0 skipped | planned | pending | final `test-results/round-2-results.json` |
| AC-3 | Round-2 contract-parity tests pass (CONTRACT-01..06) | planned | pending | `tests/e2e/round-2/contract-parity.spec.ts` |
| AC-4 | Round-2 mock-LLM tests pass (MOCK-01..03) | planned | pending | `tests/e2e/round-2/interview-mock-llm.spec.ts` |
| AC-5 | Pydantic strictness unit test passes | planned | pending | `backend/tests/unit/test_errors_schemas_strictness.py` |
| AC-6 | Auth-guard E2E passes (GUARD-01..04) | planned | pending | `tests/e2e/round-2/auth-guard.spec.ts` |
| AC-7 | All FIX-001..012 rows in this file are `done` | planned | pending | this file |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-020-1 | Job 5 fields are visible in the UI when a job row is clicked (D-014 fixed; A1 green) | planned | pending | T2 |
| SC-020-2 | `source_*` round-trips on POST and Pydantic does not silently drop unknown fields (D-002 fixed; STRICT-01/02 green) | planned | pending | T1 |
| SC-020-3 | `clear-source` is idempotent and uses PATCH (D-003/D-013 fixed; CONTRACT-01/02 green) | planned | pending | T3, T4 |
| SC-020-4 | `?source=` filter works for auto/manual/all (D-004 fixed; CONTRACT-03/04/05 green) | planned | pending | T5 |
| SC-020-5 | `/resume-branches` is the only path that 200s (D-005 fixed; CONTRACT-06 green) | planned | pending | T6 |
| SC-020-6 | `InterviewSessionCreateOut` response is the actual Pydantic shape (D-006 fixed; MOCK-01 green) | planned | pending | T7 |
| SC-020-7 | ErrorBook source filter UI is functional (D-009 fixed; D5 green) | planned | pending | T8 |
| SC-020-8 | Protected routes redirect unauthenticated visitors (D-016 fixed; E4 + GUARD-01..04 green) | planned | pending | T9 |
| SC-020-9 | `headcount` input is HTML-hard-constrained (D-017 fixed; A2 green) | planned | pending | T10 |
| SC-020-10 | Mock LLM makes 5-round interview flow E2E-runnable (D-008 fixed; MOCK-01/02/03 green) | planned | pending | T11 |
| SC-020-11 | 100/101-char `salary_range_text` boundary is covered (D-010 fixed; EDGE-06 green) | planned | pending | T12 |

## Status Roll-up

- Total requirements: 12 (FIX-001..012) + 7 AC + 11 SC = 30 rows.
- All rows start at `planned`.
- A row moves to `done` only when the linked task in `tasks.md` is verified.
- A row moves to `blocked` if a Round-1 defect turns out to have a deeper
  cause (e.g., the schema drift is wider than one field).
