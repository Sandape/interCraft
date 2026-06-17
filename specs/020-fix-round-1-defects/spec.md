# 020 Fix Round-1 Defects

## 1. Overview

This feature fixes the 12 active defects discovered during Round-1 E2E testing of
`specs/019-cross-module-linking`. It does not introduce new product behavior;
it restores the user stories that 019 promised but the implementation never
fully delivered, and it hardens the contract/UI boundaries that 019 left
inconsistent.

Round-1 (`docs/testing/round-1/04-summary-report.md`) reported
**34 passed / 9 failed / 0 skipped** across 43 Playwright E2E cases. Every
failed case maps to a real product defect documented in
`docs/testing/round-1/03-defect-report.md`. The defect catalog D-001 ~ D-017
includes 12 active defects (P0×1, P1×6, P2×4, P3×1) and 3 archived defects
(D-001, D-011, D-015) that are already resolved or are downstream effects of
resolved root causes.

## 2. Goals

| # | Goal | Source |
|---|---|---|
| G1 | Restore `JobsDetailPanel` mount so the 5 new job fields are visible in the UI and the Job → Resume / Job → Interview CTAs are reachable from the Jobs list | D-014 (P1) |
| G2 | Make Pydantic v2 the line of defense, not a silent dropper: write schemas must explicitly accept every contract field the round-1 API surface advertised | D-002 (P0) |
| G3 | Make `clear-source` semantically distinct from `delete` and idempotent for repeated calls | D-013 (P1) |
| G4 | Reconcile 4 contract inconsistencies between `019-cross-module-linking/contracts/*.md` and the implementation: HTTP method (D-003), query param name (D-004), resume branch path (D-005), and the `InterviewSessionCreateOut` response shape (D-006) | D-003 / D-004 / D-005 / D-006 (P1) |
| G5 | Close the UX gaps: Error Book source filter UI (D-009), `/jobs` auth guard (D-016), `headcount` HTML constraints (D-017) | D-009 / D-016 / D-017 (P2) |
| G6 | Make Phase 4 5-round interview flow E2E-runnable without a live LLM key | D-008 (P2) |
| G7 | Cover the 100-char `salary_range_text` UTF-8 boundary | D-010 (P3) |
| G8 | Final E2E run reports 0 fail and 0 skip; new Round-2 contract/parity tests pass | derived from G1-G7 |

## 3. Non-Goals

- Do not change the 5 new job field semantics, types, or defaults (those are
  frozen by 019).
- Do not change the 014 job status machine.
- Do not change the 016 error book delete behavior.
- Do not change the 006 ability profile aggregation.
- Do not add new product features (e.g., 002 resume editor, 004 phase 5
  subgraphs, 005 phase 6 global capabilities).
- Do not refactor the `dbq.py` script beyond what D-015 already completed.

## 4. Defect → Requirement Mapping

Each requirement is identified by `FIX-NNN` and has a 1:1 defect anchor in
Round-1's `03-defect-report.md`. The "Round-1 failure evidence" column names
the test case that surfaced the defect, so the fix can be verified by rerunning
the same case.

| Requirement | Summary | Defect | Priority | Round-1 Failure Evidence | Status |
|---|---|---|---|---|---|
| FIX-001 | `CreateErrorQuestionInput` accepts `source_session_id` and `source_question_id` on POST | D-002 | P0 | S5 (smoke) | planned |
| FIX-002 | Mount `JobsDetailPanel` into `src/pages/Jobs.tsx` (row onClick + conditional render) | D-014 | P1 | A1, B1, B4, C1, C6 (5 cases) | planned |
| FIX-003 | `clear-source` is idempotent: second call returns 400 `source_already_cleared` | D-013 | P1 | D4 (full-error-source) | planned |
| FIX-004 | `clear-source` uses `PATCH` (REST-correct) and the doc is updated accordingly | D-003 | P1 | contract drift (no test) | planned |
| FIX-005 | `GET /error-questions` accepts `?source=` (FastAPI alias updated to allow both `?source=` and `?filter[source]=`) | D-004 | P1 | contract drift (no test) | planned |
| FIX-006 | `POST /resume-branches` path matches the contracts; or contracts are updated to match implementation; choose one and update both | D-005 | P1 | contract drift (no test) | planned |
| FIX-007 | `POST /interview-sessions` returns the Pydantic `InterviewSessionCreateOut` payload (no ORM-leak, `checkpoint_ns` present, `job_id` present) | D-006 | P1 | covered by S4 / C1 | planned |
| FIX-008 | `ErrorBook.tsx` list shows source filter (全部 / 来自面试 / 手动录入) and per-row "来自 XX" badge with removal action | D-009 | P2 | D5 (full-error-source) | planned |
| FIX-009 | `src/router.tsx` adds an auth guard for `/jobs`, `/resumes`, `/error-book`, `/interview`, `/profile`; unauthenticated visitors get `redirect('/login')` | D-016 | P2 | E4 (full-permissions) | planned |
| FIX-010 | `headcount` input has `type="number"` + `min={1}` + `step={1}` matching the backend Pydantic `ge=1` | D-017 | P2 | A2 (full-jobs-fields) | planned |
| FIX-011 | Phase 4 Mock LLM is wired into `InterviewLive` so 5-round flow runs deterministically when `VITE_USE_MOCK=true` | D-008 | P2 | G1 (chain) | planned |
| FIX-012 | New E2E covers 100-char `salary_range_text` UTF-8 boundary (including the `30-50K · 16薪` example) | D-010 | P3 | new (edge suite) | planned |

## 5. Functional Requirements

### 5.1 Backend Write-Schema Hardening (FIX-001, FIX-007)

**FIX-001** `backend/app/modules/errors/schemas.py` adds
`source_session_id: UUID | None = None` and
`source_question_id: UUID | None = None` to `CreateErrorQuestionInput`. The
fields round-trip in the response and are persisted via the existing
`error_questions` columns and partial unique index.

**FIX-007** `backend/app/modules/interviews/api.py` `create_session` returns a
real `InterviewSessionCreateOut` Pydantic instance (or the response is built via
`InterviewSessionCreateOut.model_validate(...)`), not a dict wrapping an ORM
object. The response shape is exactly:

```json
{
  "data": {
    "id": "<uuid>",
    "status": "pending",
    "thread_id": "<uuid>",
    "checkpoint_ns": "<str|null>",
    "job_id": "<uuid|null>",
    "branch_id": "<uuid|null>"
  }
}
```

### 5.2 Backend Service-Layer Idempotency (FIX-003)

**FIX-003** `backend/app/modules/errors/service.py` `clear_source` raises
`HTTPException(400, "source_already_cleared")` when both `source_session_id`
and `source_question_id` are already `NULL`. The error body uses the project
standard `{ "error": { "code": "source_already_cleared", "message": "..." } }`
format.

### 5.3 Contract Reconciliation (FIX-004, FIX-005, FIX-006)

**FIX-004** `POST /api/v1/error-questions/{id}/clear-source` is replaced by
`PATCH /api/v1/error-questions/{id}/clear-source` in the backend. The frontend
`useErrorQuestionMutations.ts` is updated. `019-cross-module-linking/contracts/
error-questions-source.md §2.1` is unchanged.

**FIX-005** `GET /api/v1/error-questions` accepts both `?source=auto|manual|all`
and `?filter[source]=auto|manual|all`. The FastAPI alias is updated to read
`Query(alias="source")` with a separate `filter[source]` alias for backward
compatibility. The frontend is migrated to `?source=`. The contract doc is
updated to show `?source=` as the canonical form.

**FIX-006** Decision: the implementation path `/resume-branches` wins (it is
already shipped and the frontend depends on it). The contract docs
(`019-cross-module-linking/contracts/*.md` and `quickstart.md §3.1.1`) are
updated to use `/resume-branches`.

### 5.4 Frontend Mounting (FIX-002)

**FIX-002** `src/pages/Jobs.tsx`:

1. Imports `JobsDetailPanel` from `@/components/jobs/JobsDetailPanel`.
2. Adds `selectedJobId` state.
3. Wires `<tr data-testid="job-row-{id}">` to `onClick={() => setSelectedJobId(j.id)}`.
4. Conditionally renders `<JobsDetailPanel job={selectedJob} onClose={...} />`
   when `selectedJobId` is set.
5. The detail panel exposes the same `data-testid` set that the component
   already declares (`job-detail-panel`, `job-detail-resume-cta`,
   `job-detail-interview-cta`, `job-detail-requirements-md`).

A `useEffect` logs a `console.warn` if `JobsDetailPanel` is ever imported but
not rendered (catches the "dead component" regression for next time).

### 5.5 Frontend UI Completions (FIX-008, FIX-009, FIX-010)

**FIX-008** `src/pages/ErrorBook.tsx`:

1. List header gains a `data-testid="error-source-filter"` segmented control
   with three options: 全部 / 来自面试 / 手动录入.
2. Each row with a non-null `source_session_id` shows a
   `data-testid="error-source-badge"` badge "来自 {company} · {position} ·
   {时间}".
3. The existing 016 remove-source button (`D-009` UI side) reuses the badge as
   its anchor.

**FIX-009** `src/router.tsx` adds a `requireAuth` loader that throws
`redirect('/login')` when `localStorage.getItem('access_token')` is absent. The
loader is applied to the following routes: `/jobs`, `/resumes`,
`/resumes/branches/:id?`, `/error-book`, `/interview`, `/interview/:id`,
`/profile`, `/profile/:dim?`.

**FIX-010** `src/pages/Jobs.tsx` 「招聘人数」`<Input>`:

```tsx
<Input
  type="number"
  min={1}
  step={1}
  inputMode="numeric"
  value={headcount}
  onChange={(e) => setHeadcount(e.target.value.replace(/[^0-9]/g, ''))}
  placeholder="如:5"
  data-testid="job-create-headcount"
/>
```

The same change is mirrored in the Job edit modal.

### 5.6 Test Infrastructure (FIX-011, FIX-012)

**FIX-011** `tests/e2e/fixtures/mock-llm.ts` is wired into the
`InterviewLive` page via `page.routeWebSocket` when
`process.env.VITE_USE_MOCK === 'true'`. The mock streams 5 deterministic
rounds with the existing `MOCK_ROUNDS` definitions. Each round's score is
parameterized so tests can force < 6 to trigger the auto-deposit path.

**FIX-012** A new E2E case `EDGE-06` is added to `full-edge.spec.ts` that
posts a Job with `salary_range_text` of exactly 100 chars and 101 chars
(respectively 200 and 100 UTF-8 characters in the
`30-50K · 16薪` template repeated), and asserts:

- 100 chars → 201
- 101 chars → 422 with `salary_range_text` in the error path
- 100-char UI rendering shows the full string without truncation

## 6. User Stories

| ID | Story | Acceptance |
|---|---|---|
| US-FIX-1 | As a hiring manager, when I click a row in `/jobs`, the detail panel opens and I can see the 5 new fields (location, requirements, type, salary, headcount). | FIX-002 verified by A1 pass |
| US-FIX-2 | As a job seeker, when I create a resume branch from a Job, the Job row shows the bound branch name and the interview CTA becomes clickable. | FIX-002 verified by B2 pass |
| US-FIX-3 | As a job seeker, when I report a low-score interview question, the system records `source_session_id` and `source_question_id` so I can trace it back later. | FIX-001 verified by S5 pass |
| US-FIX-4 | As a job seeker, when I clear the source of an error question and then click the button again, the second click is rejected with a clear `source_already_cleared` error. | FIX-003 verified by D4 pass |
| US-FIX-5 | As a recruiter, when I open `/jobs` while logged out, I am redirected to `/login` instead of seeing an empty loading state. | FIX-009 verified by E4 pass |
| US-FIX-6 | As a job seeker, when I view `/error-book`, I can filter the list by "来自面试" or "手动录入" so I can focus on the questions I want to review. | FIX-008 verified by D5 pass |
| US-FIX-7 | As a job seeker, when I add a job with 0 or negative headcount, the form blocks my input client-side (no round-trip to the server). | FIX-010 verified by A2 pass |

## 7. Acceptance Criteria

The feature is **done** when all of the following are true:

| # | Criterion | Verification |
|---|---|---|
| AC-1 | All 12 active defects (D-002, D-003, D-004, D-005, D-006, D-008, D-009, D-010, D-013, D-014, D-016, D-017) are closed in the implementation. | `git log` shows fix commits referencing each defect ID; defect report status flipped to `fixed`. |
| AC-2 | Round-1's 43 Playwright E2E cases report **43 passed / 0 failed / 0 skipped** when rerun via `mcp__playwright-test__test_run`. | `test-results/round-2-results.json` shows 43/0/0. |
| AC-3 | New Round-2 contract tests pass (see §8). | `mcp__playwright-test__test_run` on `tests/e2e/round-2/contract-parity.spec.ts` reports 0 failed. |
| AC-4 | New Round-2 mock-LLM E2E passes (5 rounds + auto-deposit). | `mcp__playwright-test__test_run` on `tests/e2e/round-2/interview-mock-llm.spec.ts` reports 0 failed. |
| AC-5 | `backend/app/modules/errors/schemas.py` write schema regression test added: posting unknown fields is rejected (or recorded) instead of silently dropped. | `backend/tests/unit/test_errors_schemas_strictness.py` passes. |
| AC-6 | Auth guard E2E added for at least `/jobs`, `/error-book`, `/resumes`. | `mcp__playwright-test__test_run` on `tests/e2e/round-2/auth-guard.spec.ts` reports 0 failed. |
| AC-7 | `requirements-status.md` rows for FIX-001 to FIX-012 are all `done`. | status table review. |

## 8. Round-2 Test Plan (delta on top of Round-1)

| Test file | Cases | Purpose |
|---|---|---|
| `tests/e2e/round-2/contract-parity.spec.ts` | CONTRACT-01, 02, 03 | Verifies D-003 (PATCH clear-source), D-004 (`?source=` accepted), D-005 (resume-branches path). Each case fires a request that the contract doc promises and asserts 2xx. |
| `tests/e2e/round-2/auth-guard.spec.ts` | GUARD-01, 02, 03, 04 | Verifies D-016 for `/jobs`, `/resumes`, `/error-book`, `/interview`. Each case visits a route in a clean context (no token) and asserts `redirect('/login')`. |
| `tests/e2e/round-2/interview-mock-llm.spec.ts` | MOCK-01, 02, 03 | Verifies D-008: 5 rounds with `VITE_USE_MOCK=true`, last round score 4 → `error_questions` row created with `source_session_id` set (FIX-001 dependent). |
| `tests/e2e/round-2/pydantic-strictness.spec.ts` | STRICT-01, 02 | Verifies FIX-001 by sending an unknown field and asserting either 422 (strict mode) or 200 with the field present in the response (lenient mode + the field is in schema). |
| `tests/e2e/round-2/full-edge-r2.spec.ts` | EDGE-06 | Verifies D-010 100/101 char `salary_range_text` boundary. |

Total new cases: 11. Combined Round-1 + Round-2 = 54 cases.

## 9. Out of Scope

- New product features (002 / 004 / 005 / 011).
- Performance, load, penetration testing.
- Mobile responsive redesign.
- Migration of `localStorage` token to httpOnly cookie (a follow-up security
  feature, not a defect fix).
- Removal of the unused `backend/scripts/dbq_user.py` (already unreferenced but
  left in git tracking; a separate cleanup task).

## 10. Related Documents

| Type | Path |
|---|---|
| Defect source (this feature) | `docs/testing/round-1/03-defect-report.md` |
| Round-1 summary | `docs/testing/round-1/04-summary-report.md` |
| Round-1 acceptance | `docs/testing/round-1/05-acceptance-checklist.md` |
| Round-1 inventory | `docs/testing/round-1/01-requirements-inventory.md` |
| Round-1 plan | `docs/testing/round-1/02-test-plan.md` |
| Round-1 E2E code | `tests/e2e/round-1/` |
| Round-2 E2E code (to be added) | `tests/e2e/round-2/` |
| Parent feature | `specs/019-cross-module-linking/spec.md` |
| Parent data model | `specs/019-cross-module-linking/data-model.md` |
| Contracts this feature touches | `specs/019-cross-module-linking/contracts/error-questions-source.md`, `specs/019-cross-module-linking/contracts/jobs-fields.md`, `specs/019-cross-module-linking/contracts/interview-job-id.md` |
| Frontend source map | `docs/architecture/source-map.md` |
| Tooling guide | `docs/testing/README.md` |

## 11. Open Questions

1. **FIX-006 direction**: Should the path be `/resumes/branches` (multi-resource
   REST style) or `/resume-branches` (current implementation)? This spec
   defaults to "keep implementation, update contracts" because the frontend
   already calls `/api/v1/resume-branches`. If the team wants the other way,
   FIX-006 needs an extra task to add a backend alias and migrate the frontend.

2. **FIX-005 query parameter**: Should we accept both `?source=` and
   `?filter[source]=` (FastAPI alias), or just one? This spec defaults to
   "accept both, deprecate `?filter[source]=` later" because the frontend
   migration is a one-line change.

3. **FIX-011 mock LLM placement**: The mock can be injected at three layers:
   (a) `page.routeWebSocket` in the test, (b) a `VITE_USE_MOCK` env gate in
   the app code, (c) a backend `MockLLM` provider when `LLM_PROVIDER=mock`.
   This spec recommends (a) + (b) — purely a test-time concern.
