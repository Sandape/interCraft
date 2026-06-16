# 019 Requirement Status

This file separates requirement intent from implementation evidence. A row is
`done` only when implementation and verification evidence are both linked or
named. If implementation appears in the worktree but has not been verified, keep
the status as `in_progress`.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Register complete job information | in_progress | `backend/tests/unit/test_jobs_extended_fields.py` exists in worktree | Needs final test run and UI verification. |
| US2 | Create resume branch from job | in_progress | `backend/tests/integration/test_019_branch_bind.py` exists in worktree | Needs canonical E2E confirmation. |
| US3 | Start interview from job | in_progress | `backend/tests/integration/test_019_interview_job_id.py` exists in worktree | Needs live/intake and prompt verification. |
| US4 | Auto-deposit low-score interview questions into Error Book | in_progress | `backend/tests/unit/test_019_error_sink.py` and `backend/tests/integration/test_019_error_sink.py` exist in worktree | Needs clear-source and filter verification. |
| US5 | End-to-end cross-module smoke | in_progress | `tests/e2e/019-cross-module-linking.spec.ts` exists in worktree | Needs deterministic Playwright run. |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | Add 5 structured job fields | in_progress | `backend/migrations/versions/0009_019_job_fields.py` | Verify migration and API output before marking done. |
| FR-002 | Extend job create/patch/output schemas | in_progress | `backend/app/modules/jobs/schemas.py` modified | Needs schema/unit test pass. |
| FR-003 | Return and render 5 job fields | in_progress | Jobs service and UI files modified | Needs frontend verification. |
| FR-004 | Add inputs for 5 job fields | in_progress | Jobs UI modified | Needs form validation checks. |
| FR-005 | Add Job detail CTAs | in_progress | Jobs UI modified | Verify `branch_id` conditions. |
| FR-006 | Add Topbar create-from-job entry | in_progress | `src/components/layout/Topbar.tsx` modified | Verify canonical test after Playwright migration. |
| FR-007 | Prefill resume editor from `source_job_id` | in_progress | Resume files modified | Verify URL and draft behavior. |
| FR-008 | Backfill `jobs.branch_id` after branch save | in_progress | Job and resume flow modified | Verify outbox behavior. |
| FR-009 | Add `interview_sessions.job_id` | in_progress | `backend/migrations/versions/0010_019_interview_job_id.py` | Verify FK and index. |
| FR-010 | Extend interview session schemas | in_progress | Interview schema files modified | Needs API tests. |
| FR-011 | Start interview from Job detail | in_progress | Interview service/UI modified | Needs E2E. |
| FR-012 | Prefill InterviewLive intake from job | in_progress | Interview live files modified | Needs intake verification. |
| FR-013 | Inject `requirements_md` into question generation | in_progress | `backend/app/agents/interview/requirements_block.py` exists in worktree | Needs prompt unit tests and token truncation verification. |
| FR-014 | Disable interview CTA when no branch is bound | in_progress | Jobs UI modified | Needs tooltip/disabled-state verification. |
| FR-015 | Add `error_questions.source_question_id` | in_progress | `backend/migrations/versions/0011_019_error_source_question_id.py` | Verify partial unique index. |
| FR-016 | Auto-create ErrorQuestion when score is below threshold | in_progress | Error service and score node modified | Needs idempotency verification. |
| FR-017 | Add clear-source endpoint | in_progress | Error API/service files modified | Needs endpoint and UI action verification. |
| FR-018 | Expose source fields and source filter | in_progress | Error schema/repository files modified | Needs API and UI filter verification. |
| FR-019 | Add ErrorBook source UI and actions | in_progress | `src/pages/ErrorBook.tsx` modified | Needs E2E. |
| FR-020 | Add `AUTO_ERROR_THRESHOLD = 6` | in_progress | Error service modified | Verify constant location and tests. |
| FR-021 | Preserve Ability Profile aggregation link | in_progress | E2E smoke planned | Do not modify 006 aggregation logic. |
| FR-022 | Preserve 014 status/outbox behavior | in_progress | Regression tests needed | Must stay backward compatible. |
| FR-023 | Preserve 016 recall/reset/status behavior | in_progress | Regression tests needed | Auto deposit is additive only. |
| FR-024 | Preserve 006 and Phase 4 ability diagnose internals | in_progress | Regression tests needed | Data smoke only. |
| FR-025 | Do not modify ResumeBranch model | in_progress | Code review check | Prefill flow only. |
| FR-026 | Use Simplified Chinese UI copy and stable test IDs | in_progress | UI files modified | Needs UI text audit. |
| FR-027 | Add 3 Alembic migrations with down migrations | in_progress | Migration files exist in worktree | Verify downgrade paths. |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | Job fields persist and display with defaults | in_progress | Pending test run | |
| SC-002 | Job-to-resume branch binding succeeds and replays offline | in_progress | Pending E2E | |
| SC-003 | Job-started interview records `job_id` and injects requirements | in_progress | Pending backend and E2E verification | |
| SC-004 | Low-score questions auto-create without duplicates | in_progress | Pending backend tests | |
| SC-005 | Clear-source and delete behaviors are distinct | in_progress | Pending API/UI tests | |
| SC-006 | Full chain E2E: Job -> Resume -> Interview -> Error Book -> Ability Profile | in_progress | Pending deterministic Playwright run | Mock LLM may be needed. |
| SC-007 | New/changed UI copy is Simplified Chinese with stable test IDs | in_progress | Pending UI audit | |
| SC-008 | Existing 014/016/006/Phase 4 regressions remain green | in_progress | Pending full relevant test run | |

