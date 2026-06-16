# Tasks: Topbar New Resume Branch

**Input**: Design documents from `specs/017-topbar-new-resume/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md)

**Organization**: Single user story — this is a small frontend-only wiring fix.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Path Conventions

- Frontend: `src/`
- E2E: `tests/e2e/`

---

## Phase 1: Cleanup (Dead Prop Removal)

**Purpose**: Remove the unused `onNewResume` prop chain before wiring the real behavior. These tasks touch different files and can run in parallel.

- [x] T001 [P] Remove `onNewResume` prop from `src/components/layout/AppShell.tsx` — delete the prop from the interface and stop passing it to `<Topbar>`
- [x] T002 [P] Remove `onNewResume` prop from `src/components/layout/Topbar.tsx` — delete the prop from the interface and the onClick handler

**Checkpoint**: AppShell and Topbar no longer reference `onNewResume`. Topbar「新建简历分支」button is temporarily non-functional (expected).

---

## Phase 2: Wire Direct Navigation in Topbar

**Purpose**: Make the button navigate directly to `/resume?new=true`.

- [x] T003 [US1] Update `src/components/layout/Topbar.tsx` — change the「新建简历分支」button's `onClick` from `onNewResume` to `() => navigate('/resume?new=true')`. `useNavigate` is already imported and used in the file.

**Checkpoint**: Clicking the button navigates to `/resume?new=true`. The modal does NOT auto-open yet.

---

## Phase 3: Auto-Open Modal from URL (ResumeList)

**Purpose**: ResumeList reads the URL param and auto-opens the create modal.

- [x] T004 [US1] Update `src/pages/ResumeList.tsx` — import `useSearchParams` from `react-router-dom`, read `searchParams.get('new') === 'true'` on mount, and set `open = true` if the param is present. Use a `useEffect` that runs once on mount to set the open state from the URL param.
- [x] T005 [US1] Update `src/pages/ResumeList.tsx` — in the create modal's `onClose` handler (and the `onSuccess` callback of the create mutation), add URL cleanup: `setSearchParams({}, { replace: true })` to remove `?new=true` when the modal closes or the branch is created successfully.

**Checkpoint**: Clicking the topbar button navigates to `/resume?new=true`, modal auto-opens, and closing the modal cleans up the URL.

---

## Phase 4: Verify No Regressions

- [x] T006 Run `npm run typecheck` and confirm zero errors
- [x] T007 Run `npm test -- --run` and confirm all existing tests still pass

**Checkpoint**: TypeScript clean, all tests green.

---

## Phase 5: E2E Test

- [x] T008 Create `tests/e2e/topbar-new-resume.spec.ts` — Playwright test covering:
  1. Click topbar button from dashboard → verify navigate to `/resume?new=true` + modal opens
  2. Close modal → verify URL returns to `/resume`
  3. Direct access `/resume?new=true` → verify modal opens
  4. Existing「新建简历」button on ResumeList page → verify it still works and does NOT add `?new=true`
- [x] T009 Run E2E test: `npx playwright test tests/e2e/topbar-new-resume.spec.ts` and confirm all scenarios pass

---

## Dependencies & Execution Order

- **Phase 1 (T001, T002)**: No dependencies — parallel.
- **Phase 2 (T003)**: Depends on T002 (Topbar prop must be removed before wiring new behavior).
- **Phase 3 (T004, T005)**: Depends on T003 (navigation must work before modal reads URL). T004 and T005 touch the same file — sequential.
- **Phase 4 (T006, T007)**: No code dependencies — can run independently.
- **Phase 5 (T008, T009)**: Depends on all implementation tasks.

### Parallel Opportunities

- T001 and T002 in Phase 1 can run in parallel (different files).
- T006 and T007 in Phase 4 can run in parallel.

## Implementation Strategy

### Single Increment

This is a small feature with no meaningful MVP sub-slice. Implement all phases in order. The button starts dead and ends fully functional.

1. Remove dead props (Phase 1)
2. Wire navigation (Phase 2)
3. Wire auto-open modal (Phase 3)
4. Verify types + tests (Phase 4)
5. E2E test + run (Phase 5)
