# Tasks: Jobs Status Alignment

**Input**: Design documents from `/specs/015-jobs-status-alignment/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/jobs-transitions.md](./contracts/jobs-transitions.md), [quickstart.md](./quickstart.md)

**Tests**: Required by the feature specification (Constitution Principle III — Test-First). Each user story phase opens with a failing test that must turn green before the implementation tasks are considered done.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

This is a web app. Paths follow the plan.md project structure:
- Backend: `backend/app/modules/jobs/`
- Frontend: `src/api/`, `src/hooks/`, `src/components/`, `src/pages/`
- E2E: `tests/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm prerequisites and the existing test harness are usable.

- [x] T001 Verify backend Redis on `localhost:6379` and Postgres online (per `CLAUDE.md` local-env notes)
- [x] T002 Review existing jobs module: `backend/app/modules/jobs/api.py`, `backend/app/modules/jobs/service.py`, `backend/app/modules/jobs/schemas.py` to identify exact mount points
- [x] T003 [P] Review existing Jobs page: `src/pages/Jobs.tsx`, `src/components/jobs/StatusBadge.tsx`, `src/hooks/queries/useJobs.ts`, `src/repositories/JobRepository.ts` to confirm current shape
- [x] T004 [P] Review existing e2e test pattern: `tests/e2e/phase2/jobs-from-api.spec.ts` and the playwright config

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Expose the canonical `JOB_TRANSITIONS` graph over HTTP and fetch it from the frontend. Both the new endpoint and the new hook MUST be in place before any UI refactor starts.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Backend: new GET /api/v1/jobs/transitions endpoint

- [x] T005 [P] Add Pydantic schemas `TransitionEdge` and `TransitionsOut` to `backend/app/modules/jobs/schemas.py` (use `from_` + alias `from` per contracts/jobs-transitions.md)
- [x] T006 Write a failing pytest in `backend/app/modules/jobs/tests/test_transitions.py` that asserts the response shape (statuses ordered correctly, transitions flat list of 20 edges, `rejected` and `withdrawn` have no outgoing edges, 401 without auth) — must fail before T007 lands
- [x] T007 Add `get_transitions()` helper to `backend/app/modules/jobs/service.py` and `GET /api/v1/jobs/transitions` route to `backend/app/modules/jobs/api.py` — must register the route BEFORE the `/{id}` parameterized route in the same file
- [x] T008 Run `cd backend && uv run pytest -q app/modules/jobs/tests/test_transitions.py` and confirm the test from T006 now passes

### Frontend: new useJobTransitions hook

- [x] T009 [P] Add `JobTransitionsResponse` and `JobTransitionEdge` types in a new file `src/types/jobs.ts`
- [x] T010 [P] Add `getJobTransitions()` typed client to `src/api/jobs.ts` using `apiClient.request('GET', '/api/v1/jobs/transitions')`
- [x] T011 Write a failing vitest in `src/hooks/queries/__tests__/useJobTransitions.test.ts` that mocks `getJobTransitions` to return a known graph and asserts the hook returns `data.statuses` of length 7 and that `data` is non-null even when the fetch rejects (built-in fallback) — must fail before T012 lands
- [x] T012 Create `src/hooks/queries/useJobTransitions.ts` with `useQuery({queryKey:['jobTransitions'], queryFn:getJobTransitions, staleTime:Infinity, gcTime:Infinity, retry:1})` and the FALLBACK constant from `contracts/jobs-transitions.md`. Expose `{data, isStale, isLoading, refetch}`. `data` is `q.data ?? FALLBACK`
- [x] T013 Run `npm test -- src/hooks/queries/__tests__/useJobTransitions.test.ts` and confirm the test from T011 now passes

**Checkpoint**: `GET /api/v1/jobs/transitions` returns the documented shape; `useJobTransitions()` returns the graph (or the fallback) from the frontend. No UI changes yet.

---

## Phase 3: User Story 1 - Advance a job through its real lifecycle (Priority: P1) 🎯 MVP

**Goal**: A user can open a row's status popover, pick an allowed next status, and the row badge + stats update without producing any HTTP 409.

**Independent Test**: Seed one job in `applied`, click the row's `MoreHorizontal`, pick `test` from the popover, assert the row badge becomes "笔试" and the `test` tab count increments by 1. No 409s in the network log.

### Tests for User Story 1

- [x] T014 [P] [US1] Add the first failing scenario to `tests/e2e/jobs-status-alignment.spec.ts`: "advances a job from applied to test via the row popover with no 409 in the network log"

### Implementation for User Story 1

- [x] T015 [P] [US1] Update `src/components/jobs/StatusBadge.tsx`: remove the `screening` and `interview` keys; add `test` (icon `FileText`, label "笔试", variant `default`), `oa` (icon `FileText`, label "OA", variant `default`), `hr` (icon `MessageSquare`, label "HR 面", variant `warning`), and `withdrawn` (icon `XCircle`, label "已撤回", variant `outline`). Keep the unknown-status fallback that renders the raw string.
- [x] T016 [P] [US1] Create `src/components/jobs/TerminalConfirmModal.tsx` — a small `<Modal>` wrapper with title, body, and "确认"/"取消" buttons. Reuse the project's `Modal` from `src/components/ui/Modal`. Props: `{open, to, company, position, onConfirm, onCancel, isPending}`. Add `data-testid="terminal-confirm-modal"` and `data-testid="terminal-confirm-submit"`.
- [x] T017 [US1] Create `src/components/jobs/StatusPopover.tsx` — a popover anchored to a `MoreHorizontal` icon button (`data-testid="status-popover-trigger"`). On open, render one menu item per allowed `to` from `useJobTransitions().data.transitions` filtered by `from === job.status` (`data-testid="status-menuitem-{to}"`). On item click: if `to` is `rejected` or `withdrawn`, open `TerminalConfirmModal`; otherwise call `updateStatus({id: job.id, to})` directly. Close the popover on selection. Outside-click closes the popover.
- [x] T018 [US1] Update `src/pages/Jobs.tsx`: import `useJobTransitions`. Remove the old `NEXT_STATUS` constant, the per-row advance/reject icon buttons, and the `updateStatus`/`deleteJob` direct calls. Replace each `JobRow`'s action cell with `<StatusPopover job={job} onUpdate={(to) => updateStatus.mutate({id: job.id, to})} />`. Track per-row mutation state via a `Record<string, { pending: boolean, error: string | null }>` in the page state.
- [x] T019 [US1] Run `tests/e2e/jobs-status-alignment.spec.ts` scenario 1 — must pass; verify no 409s in the network log via `page.on('response', …)`.

**Checkpoint**: US1 is independently functional. Users can move a job from `applied` to any allowed next status via a popover, and the backend never sees a 409 from this page.

---

## Phase 4: User Story 2 - Filter the job list by real status (Priority: P1)

**Goal**: The status tab set is `['all', ...useJobTransitions().data.statuses]`. Each tab shows a count badge from the existing `useJobStats().counts[status]`.

**Independent Test**: Seed one job in each of the seven statuses, click each tab in order, assert only the matching row(s) are visible and the tab count badge matches the row count.

### Tests for User Story 2

- [x] T020 [P] [US2] Add a failing scenario to `tests/e2e/jobs-status-alignment.spec.ts`: "filters jobs by each real status tab and shows the correct count badge"

### Implementation for User Story 2

- [x] T021 [US2] Update `src/pages/Jobs.tsx`: replace the hard-coded `STATUS_TABS` array with a derived one from `useJobTransitions().data.statuses`. Prepend an `{key:'all', label:'全部', count: statsData?.total ?? jobs.length}` entry. Map each `status` to `{key:status, label: STATUS_LABELS[status], count: counts[status] ?? 0}`. Add `data-testid="status-tab-{key}"` to each rendered tab.
- [x] T022 [P] [US2] Add a small `STATUS_LABELS` map at the top of `src/pages/Jobs.tsx` matching the Chinese labels from the spec: `{applied:'已投递', test:'笔试', oa:'OA', hr:'HR 面', offer:'Offer', rejected:'已拒', withdrawn:'已撤回'}`. The hook's fallback is the only source of `statuses`, so this map is keyed by every status the hook can return.
- [x] T023 [US2] Run `tests/e2e/jobs-status-alignment.spec.ts` scenario 2 — must pass.

**Checkpoint**: US2 is independently functional. The tab set is derived from the hook; no `screening` or `interview` tab appears anywhere.

---

## Phase 5: User Story 3 - See accurate stats including withdrawn (Priority: P2)

**Goal**: Five stat tiles in lifecycle order, no overlap, derived from `useJobStats().counts`.

**Independent Test**: Seed 2 withdrawn + 1 rejected, open Jobs, assert the "已撤回" tile shows `2` and the "已拒绝" tile shows `1`.

### Tests for User Story 3

- [x] T024 [P] [US3] Add a failing scenario to `tests/e2e/jobs-status-alignment.spec.ts`: "splits withdrawn from rejected in the stats tiles"

### Implementation for User Story 3

- [x] T025 [US3] Update `src/pages/Jobs.tsx`: rewrite the `counts` object to expose `total`, `active` (= `applied + test + oa + hr`), `offer`, `rejected`, `withdrawn` directly from `statsData.counts` (no arithmetic across terminal states). Add a new `KanbanStat` for "已撤回" with `value={String(counts.withdrawn)}` and the same `XCircle` icon as "已拒绝" but a different label. Render the 5 tiles in this grid order: `总申请`, `进行中`, `Offer`, `已拒绝`, `已撤回` (the grid uses `grid-cols-2 md:grid-cols-5`).
- [x] T026 [US3] Run `tests/e2e/jobs-status-alignment.spec.ts` scenario 3 (stats split) — must pass.

**Checkpoint**: US3 is independently functional. Stats are accurate and "已撤回" no longer collapses into "已拒绝".

---

## Phase 6: User Story 4 - Recover from an invalid transition with inline feedback (Priority: P2)

**Goal**: When the backend returns 409 for a status change the UI offered, the row shows an inline error with a "重试" affordance and keeps its previous status.

**Independent Test**: Use `page.route()` to make `PATCH /api/v1/jobs/*/status` return 409, click a transition, assert the row badge is unchanged, an inline error appears, and a "重试" button is visible.

### Tests for User Story 4

- [x] T027 [P] [US4] Add a failing scenario to `tests/e2e/jobs-status-alignment.spec.ts`: "shows an inline error with retry affordance when the status update returns 409"

### Implementation for User Story 4

- [x] T028 [US4] Update `src/components/jobs/StatusPopover.tsx`: accept an `error` and `onRetry` prop. When `error` is non-null, render the error message and a "重试" button (`data-testid="status-popover-retry"`) below the menu items. The retry callback re-fires the same `updateStatus` with the last `to` value.
- [x] T029 [US4] Update `src/pages/Jobs.tsx`: in the per-row mutation state map, capture `error` from `updateStatus.mutate` failures (`onError`). Surface the error to the matching row's `StatusPopover` via props. Do NOT optimistically update the row badge; only mutate it on `onSuccess`. Add `data-testid="row-error-{job.id}"` for the error string.
- [x] T030 [US4] Update `src/repositories/__tests__/JobRepository.test.ts`: replace the fixture's `counts: { applied: 2, screening: 1, interview: 0, ... }` with real backend statuses (`{ applied: 2, test: 1, oa: 0, hr: 0, offer: 0, rejected: 0, withdrawn: 0 }`) and update the matching test assertions.
- [x] T031 [US4] Run `tests/e2e/jobs-status-alignment.spec.ts` scenario 4 (409 retry) — must pass.

**Checkpoint**: US4 is independently functional. Any 409 surfaces inline feedback with a one-click retry, and the row never silently rolls back.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Make the slice production-ready: typecheck clean, no `screening`/`interview` strings anywhere, the stale-data banner appears only on real errors, and the contract is exercised end-to-end.

- [x] T032 Remove the unused `MoreHorizontal` and `ChevronDown` imports from `src/pages/Jobs.tsx` (if no longer used) and confirm no remaining references to `screening` or `interview` exist anywhere in `src/`
- [x] T033 [P] Add a non-blocking banner at the top of `src/pages/Jobs.tsx` (only visible when `useJobTransitions().isStale` is true): text "状态数据可能已过期，部分状态不可用 — 重试" with a "重试" button that calls `refetch()`. Add `data-testid="transitions-stale-banner"`.
- [x] T034 [P] Update `tests/e2e/jobs-status-alignment.spec.ts` with a final scenario "no phantom tabs" — assert the rendered tab list equals exactly `['all','applied','test','oa','hr','offer','rejected','withdrawn']` and the strings `screening` and `interview` are not present in the page DOM
- [x] T035 [P] Run `npm run typecheck` and confirm zero errors
- [x] T036 [P] Run `cd backend && uv run pytest -q` and confirm the new `test_transitions.py` plus the existing jobs tests all pass (3/3 jobs tests pass; 19 pre-existing failures in test_ability_profile.py unrelated to Feature 015)
- [x] T037 Run the full e2e spec `npx playwright test tests/e2e/jobs-status-alignment.spec.ts` and confirm all scenarios pass
- [x] T038 [P] Update `specs/015-jobs-status-alignment/quickstart.md` if the curl commands diverged from what actually shipped (e.g., new env var, new path)

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup. T005, T009, T010 can run in parallel. T006 must precede T007/T008; T011 must precede T012/T013.
- **US1 (Phase 3)**: Depends on Phase 2 (the hook is needed for the popover). T015, T016 can run in parallel. T017 depends on T015/T016 and the hook from Phase 2. T018 depends on T017.
- **US2 (Phase 4)**: Depends on Phase 2 and US1's `StatusPopover` (the tabs and the popover share the same `statuses` derivation). T020 precedes T021/T022.
- **US3 (Phase 5)**: Depends on Phase 2 only (uses `useJobStats`, not the popover). T024 precedes T025.
- **US4 (Phase 6)**: Depends on US1 (the popover must exist) and US2 (the tabs need to use real statuses). T027 precedes T028/T029. T030 is independent and can run in parallel.
- **Polish (Phase 7)**: Depends on all story phases.

### Parallel opportunities

Within Phase 2:
- T005 (backend schema) and T009 + T010 (frontend types + client) touch different files and can run in parallel.

Within US1 (Phase 3):
- T015 (StatusBadge) and T016 (TerminalConfirmModal) touch different files and can run in parallel.

Within US4 (Phase 6):
- T030 (the vitest fixture update) touches a different file from T028/T029 and can run in parallel.

Within Polish (Phase 7):
- T033, T034, T035, T036, T038 are all in different files and can run in parallel once their prereqs land.

## Implementation Strategy

### MVP first (US1 only)

Ship US1 alone if time is tight. That removes the broken 409 path and gives users a working row-level status menu. US2/US3/US4 can land as follow-up increments because the row popover and the hook are already in place from the foundational phase.

### Incremental delivery

1. **Phase 2 (Foundational)**: backend endpoint + frontend hook — invisible to users but unblocks everything.
2. **Phase 3 (US1)**: working popover with no 409s — the most visible user-facing fix.
3. **Phase 4 (US2)**: corrected tab set — surfaces the previously hidden statuses.
4. **Phase 5 (US3)**: split stats — fixes the misleading tile.
5. **Phase 6 (US4)**: 409 retry — defensive UX.
6. **Phase 7 (Polish)**: cleanup, banner, full e2e coverage.
