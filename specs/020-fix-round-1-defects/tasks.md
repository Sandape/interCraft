# 020 Tasks

Tasks are ordered P0 → P1 → P2 → P3 with explicit dependencies. Each task
follows the test-first order of the project: the failing test from Round-1
(or a new Round-2 test) is named first, the fix is named second, and
verification runs third.

A task is **done** when:
- The implementation change is in the worktree.
- The named Round-1 case reruns and passes.
- Any required Round-2 case passes.
- The defect row in `docs/testing/round-1/03-defect-report.md` is updated
  to status `fixed` with the fix commit reference.

## Task Dependency Graph

```
T1 (FIX-001, P0) ─────────────────────┐
                                        ↓
T4 (FIX-004, P1, clear-source PATCH) ──┤
                                        ↓
T3 (FIX-003, P1, clear-source idempotency) ─────┐
                                                  ↓
T5 (FIX-005, P1, ?source=) ──────────────────────┤
                                                  ↓
T11 (FIX-011, P2, Mock LLM)  ──────────────────┴──→ T7 (FIX-007, P1) ← verify with MOCK-01
                                                                                
T2 (FIX-002, P1)         ──── independent ───────────────────┐
T6 (FIX-006, P1)         ──── independent ───────────────────┤
T8 (FIX-008, P2)         ──── depends on T1 + T3 (UI shows FIX-001 result + FIX-003 button)
T9 (FIX-009, P2)         ──── independent ──────────────────┤
T10 (FIX-010, P2)        ──── independent ──────────────────┤
T12 (FIX-012, P3)        ──── independent ─────────────────┘
```

Wave order for code review / merge:

| Wave | Tasks | Notes |
|---|---|---|
| 1 | T1, T4, T3, T5, T7 | All error_questions and interview-session backend fixes. Can land in one PR. |
| 2 | T2 | Frontend mount. Single file change. |
| 3 | T6 | Doc-only. |
| 4 | T8, T9, T10 | UI cleanups. |
| 5 | T11 | Test infrastructure. |
| 6 | T12 | Coverage. |

## T1 — FIX-001 / D-002 (P0): `CreateErrorQuestionInput` 写端 schema

**Defect**: `D-002` `CreateErrorQuestionInput` silently drops
`source_session_id` and `source_question_id` on POST.

**Files**:
- `backend/app/modules/errors/schemas.py` (add two fields)
- `backend/app/modules/errors/service.py` (no behavior change; the repo
  `create` method already accepts the kwargs)
- `backend/app/modules/errors/repo.py` (no change)

**Round-1 test (rerun)**: `tests/e2e/round-1/smoke.spec.ts` `S5` — auto-deposit
S5 expects `source_session_id` to round-trip. After the fix, the smoke
helper must be updated to POST with `source_session_id` set; today it
sets the value via direct SQL.

**Round-2 test (new)**: `tests/e2e/round-2/pydantic-strictness.spec.ts`
`STRICT-01` and `STRICT-02`. See `contracts/error-questions-source.md` §5.

**Backend unit test (new)**:
- `backend/tests/unit/test_errors_schemas_strictness.py` — POST with valid
  `source_session_id` and `source_question_id`; the service layer must
  persist the values.

**Verify**:
- `cd backend && uv run pytest tests/unit/test_errors_schemas_strictness.py -q`
- `mcp__playwright-test__test_run` on `tests/e2e/round-1/smoke.spec.ts`
  S5: pass
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/pydantic-strictness.spec.ts` STRICT-01/02: pass

**Definition of done**: 03-defect-report.md `D-002` row status set to
`fixed` with the commit hash.

## T2 — FIX-002 / D-014 (P1): Mount `JobsDetailPanel`

**Defect**: `D-014` `JobsDetailPanel` component is fully built and unit-tested
but never imported into `src/pages/Jobs.tsx`. Five E2E cases blocked.

**Files**:
- `src/pages/Jobs.tsx` — add import, state, onClick, conditional render
- `src/components/jobs/JobsDetailPanel.tsx` — add the dev-only mount-warning
  useEffect from `contracts/jobs-frontend-integration.md` §2.2

**Round-1 tests (rerun)**: A1, B1, B4, C1, C6 (5 cases).

**Verify**:
- `npm run typecheck` — 0 errors
- `npm run test -- JobsDetailPanel` — unit test still passes
- `mcp__playwright-test__test_run` on `tests/e2e/round-1/full-jobs-fields.spec.ts`
  A1: pass
- `mcp__playwright-test__test_run` on `tests/e2e/round-1/full-resume-binding.spec.ts`
  B1, B4: pass
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-1/full-interview-job.spec.ts` C1, C6: pass

**Definition of done**: All 5 round-1 cases pass; `D-014` row flipped to
`fixed`.

## T3 — FIX-003 / D-013 (P1): `clear-source` Idempotency

**Defect**: `D-013` `clear-source` returns 200 on every call, including
the second one when sources are already NULL.

**Files**:
- `backend/app/modules/errors/service.py` — add pre-check
- `backend/tests/integration/test_clear_source_idempotent.py` (new) — covers
  the 400 path

**Round-1 test (rerun)**: `tests/e2e/round-1/full-error-source.spec.ts` `D4`
— second call should return 400 `source_already_cleared`.

**Round-2 test (new)**: `tests/e2e/round-2/contract-parity.spec.ts`
`CONTRACT-02` — second PATCH returns 400 with the typed error code.

**Verify**:
- `cd backend && uv run pytest tests/integration/test_clear_source_idempotent.py -q`
- `mcp__playwright-test__test_run` on `full-error-source.spec.ts` D4: pass
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/contract-parity.spec.ts` CONTRACT-01, CONTRACT-02: pass

**Definition of done**: `D-013` row status = `fixed`; the 400 response
includes the `source_already_cleared` error code.

## T4 — FIX-004 / D-003 (P1): `clear-source` Method = `PATCH`

**Defect**: `D-003` `clear-source` is `POST` in implementation, `PATCH` in
contract.

**Files**:
- `backend/app/modules/errors/api.py:103` — change `@router.post` to
  `@router.patch`
- `src/repositories/ErrorQuestionRepository.ts` or wherever
  `useErrorQuestionMutations.ts` calls `clearErrorSource` — change `POST` to
  `PATCH` and update `tests/e2e/round-1/helpers/api.ts`
  `clearErrorSource()` to send `PATCH`

**Round-2 test (new)**: `tests/e2e/round-2/contract-parity.spec.ts`
`CONTRACT-01` — PATCH 200; smoke that POST returns 405.

**Verify**:
- `mcp__playwright-test__test_run` on `full-error-source.spec.ts` S5 + D3
  (rerun, should still pass)
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/contract-parity.spec.ts` CONTRACT-01: pass
- `mcp__playwright__browser_navigate` to `/api/v1/openapi.json` and grep
  that `clear-source` is now `patch`

**Definition of done**: `D-003` row status = `fixed`; the `POST` form
returns `405 Method Not Allowed`.

## T5 — FIX-005 / D-004 (P1): Source Filter Param Name

**Defect**: `D-004` `?source=` (contract) vs `?filter[source]=` (impl).

**Files**:
- `backend/app/modules/errors/api.py` — `Query(alias="source")` for the
  primary parameter; keep `filter[source]` as a deprecated alias
- `src/repositories/ErrorQuestionRepository.ts:49` — switch to `?source=`
- `specs/019-cross-module-linking/contracts/error-questions-source.md` §2.2
  — replace `?filter[source]=` with `?source=` (canonical)

**Round-1 tests (rerun)**: `tests/e2e/round-1/full-error-source.spec.ts` `D1`,
`D2` (filter cases).

**Round-2 tests (new)**: `tests/e2e/round-2/contract-parity.spec.ts`
`CONTRACT-03`, `CONTRACT-04`, `CONTRACT-05` — verify the three filter
modes via the canonical `?source=` param.

**Verify**:
- `mcp__playwright-test__test_run` on `full-error-source.spec.ts` D1, D2:
  pass
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/contract-parity.spec.ts` CONTRACT-03/04/05: pass

**Definition of done**: `D-004` row status = `fixed`; the contract doc
shows `?source=`; the alias is logged as deprecated in test logs.

## T6 — FIX-006 / D-005 (P1): Resume-Branches Path Doc Sync

**Defect**: `D-005` contract `/resumes/branches` vs impl `/resume-branches`.

**Files** (doc-only):
- `specs/019-cross-module-linking/quickstart.md` §3.1.1
- `specs/019-cross-module-linking/contracts/jobs-fields.md` §2.4
- `specs/019-cross-module-linking/spec.md` §5.7 (text only)
- `specs/019-cross-module-linking/plan.md` §3.1
- `specs/019-cross-module-linking/contracts/error-questions-source.md` §5
  (anchor text)

**Round-2 test (new)**: `tests/e2e/round-2/contract-parity.spec.ts`
`CONTRACT-06` — POST to `/resume-branches` returns 201; the equivalent
`/resumes/branches` returns 404.

**Verify**:
- `grep -rn "/resumes/branches" specs/019-cross-module-linking/` returns no
  matches (after the edits)
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/contract-parity.spec.ts` CONTRACT-06: pass

**Definition of done**: `D-005` row status = `fixed`; the doc
discrepancy is closed.

## T7 — FIX-007 / D-006 (P1): `InterviewSessionCreateOut` Response

**Defect**: `D-006` `POST /interview-sessions` returns a dict wrapping an
ORM object, bypassing the Pydantic `response_model`. `checkpoint_ns` and
filtered fields do not appear in the response.

**Files**:
- `backend/app/modules/interviews/api.py` — return
  `{"data": InterviewSessionCreateOut.model_validate(result).model_dump()}`

**Round-1 test (rerun)**: `tests/e2e/round-1/smoke.spec.ts` `S4` — the
assertion `expect(data.job_id).toBe(JOB_ID)` already passes after the
backend restart that fixed D-011, but D-006 is the underlying cause of
why the original round 0 failed; the contract should now be enforced
shape-wise.

**Round-2 test (new)**: `tests/e2e/round-2/interview-mock-llm.spec.ts`
`MOCK-01` — first response payload has all six required fields
(`id, status, thread_id, checkpoint_ns, job_id, branch_id`); no
`position`, `company`, `mode`, `started_at`, `ended_at`,
`duration_sec`, `overall_score`, `created_at`, `updated_at` leak.

**Verify**:
- `mcp__playwright-test__test_run` on `smoke.spec.ts` S4: pass
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/interview-mock-llm.spec.ts` MOCK-01: pass
- Manual: `curl .../interview-sessions` and assert response has exactly
  6 keys under `data`

**Definition of done**: `D-006` row status = `fixed`; the response shape
matches `InterviewSessionCreateOut` exactly.

## T8 — FIX-008 / D-009 (P2): ErrorBook Source Filter UI

**Defect**: `D-009` `ErrorBook.tsx` lacks the source filter UI even though
the backend filter works.

**Files**:
- `src/pages/ErrorBook.tsx` — add segmented control + per-row badge
- `src/components/errors/ErrorSourceBadge.tsx` (new, optional) — small
  component for the badge
- `src/repositories/ErrorQuestionRepository.ts` — already passes
  `?filter[source]=`; T5 migrates it to `?source=`

**Round-1 test (rerun)**: `tests/e2e/round-1/full-error-source.spec.ts` `D5`
— clear-source then assert badge disappears.

**Round-2 test (new)**: `tests/e2e/round-2/contract-parity.spec.ts` already
covers the API side; for the UI, a new case in `full-error-source.spec.ts`
extension or a new `tests/e2e/round-2/error-source-ui.spec.ts` that
verifies the segmented control toggles the list.

**Verify**:
- `npm run typecheck` — 0 errors
- `mcp__playwright-test__test_run` on `full-error-source.spec.ts` D5: pass
- New `error-source-ui.spec.ts` (Round-2): pass

**Definition of done**: `D-009` row status = `fixed`; the UI badge and
filter are functional in `http://localhost:5173/error-book`.

## T9 — FIX-009 / D-016 (P2): Auth Guard

**Defect**: `D-016` `/jobs` (and other protected routes) does not redirect
unauthenticated visitors to `/login`.

**Files**:
- `src/router.tsx` — add `requireAuth` loader; apply to protected routes
- `src/lib/requireAuth.ts` (new, optional) — extract the loader function

**Round-1 test (rerun)**: `tests/e2e/round-1/full-permissions.spec.ts` `E4`.

**Round-2 tests (new)**: `tests/e2e/round-2/auth-guard.spec.ts` `GUARD-01`
through `GUARD-04`.

**Verify**:
- `npm run typecheck` — 0 errors
- `mcp__playwright-test__test_run` on `full-permissions.spec.ts` E4: pass
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/auth-guard.spec.ts` GUARD-01/02/03/04: pass

**Definition of done**: `D-016` row status = `fixed`; the 4 protected
routes redirect unauthenticated visitors.

## T10 — FIX-010 / D-017 (P2): `headcount` HTML Constraints

**Defect**: `D-017` `headcount` input lacks `type="number"` + `min="1"`.

**Files**:
- `src/pages/Jobs.tsx` — add `type`, `min`, `step` to the create and edit
  `headcount` `<Input>` elements

**Round-1 test (rerun)**: `tests/e2e/round-1/full-jobs-fields.spec.ts` `A2`.

**Verify**:
- `mcp__playwright-test__test_run` on `full-jobs-fields.spec.ts` A2: pass
- Manual: `curl` returns the modal HTML and grep `type="number" min="1"`
  on the `data-testid="job-create-headcount"` element

**Definition of done**: `D-017` row status = `fixed`; the input has the
HTML hard constraints.

## T11 — FIX-011 / D-008 (P2): Phase 4 Mock LLM

**Defect**: `D-008` 5-round interview flow cannot be E2E-tested without a
live LLM key.

**Files**:
- `tests/e2e/fixtures/mock-llm.ts` — already has `MOCK_ROUNDS`; wire it
  into `page.routeWebSocket`
- `src/pages/InterviewLive.tsx` — read `import.meta.env.VITE_USE_MOCK` and
  branch to mock stream

**Round-2 tests (new)**: `tests/e2e/round-2/interview-mock-llm.spec.ts`
`MOCK-01`, `MOCK-02`, `MOCK-03`.

**Verify**:
- `npm run typecheck` — 0 errors
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/interview-mock-llm.spec.ts` MOCK-01/02/03: pass
- Manual: `VITE_USE_MOCK=true npm run dev` and complete one interview;
  the questions and answers come from `MOCK_ROUNDS` and `ability_dimensions`
  updates are visible

**Definition of done**: `D-008` row status = `fixed`; the interview flow
runs to completion in mock mode without external network calls.

## T12 — FIX-012 / D-010 (P3): 100-char `salary_range_text` Boundary

**Defect**: `D-010` 100-char UTF-8 boundary not covered.

**Files**:
- `tests/e2e/round-2/full-edge-r2.spec.ts` (new) — add `EDGE-06`

**Verify**:
- `mcp__playwright-test__test_run` on
  `tests/e2e/round-2/full-edge-r2.spec.ts` EDGE-06: pass

**Definition of done**: `D-010` row status = `fixed`; the boundary is
covered.

## Final Verification

Once all 12 tasks are done:

| Verification | Command | Expected |
|---|---|---|
| Round-1 rerun | `mcp__playwright-test__test_run({ locations: ['tests/e2e/round-1'], projects: ['chromium'] })` | 43 passed / 0 failed / 0 skipped |
| Round-2 new tests | `mcp__playwright-test__test_run({ locations: ['tests/e2e/round-2'], projects: ['chromium'] })` | 11 passed / 0 failed / 0 skipped |
| Backend unit/integration | `cd backend && uv run pytest -q` | All green |
| Frontend type check | `npm run typecheck` | 0 errors |
| Frontend build | `npm run build` | success |
| Frontend unit | `npm run test` | All green |
| Defect report update | manual edit `03-defect-report.md` | All 12 active rows status = `fixed`; defect IDs D-002, D-003, D-004, D-005, D-006, D-008, D-009, D-010, D-013, D-014, D-016, D-017 |
