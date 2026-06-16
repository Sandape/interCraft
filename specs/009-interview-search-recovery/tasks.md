# Tasks: Interview Search Recovery

**Input**: Design documents from `/specs/009-interview-search-recovery/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/interview-search-ui.md](./contracts/interview-search-ui.md), [quickstart.md](./quickstart.md)

**Tests**: Required by the feature specification and constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current feature context and existing files.

- [X] T001 Verify `.specify/feature.json` points to `specs/009-interview-search-recovery`
- [X] T002 Confirm existing interview list search state in `src/pages/InterviewList.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create deterministic E2E fixtures used by all stories.

- [X] T003 [P] Create authenticated populated-history route fixtures in `tests/e2e/interview-search-recovery.spec.ts`
- [X] T004 [P] Create authenticated empty-history route fixtures in `tests/e2e/interview-search-recovery.spec.ts`

**Checkpoint**: E2E harness can open `/interview` with deterministic populated and empty history states.

---

## Phase 3: User Story 1 - Filter interview history (Priority: P1) MVP

**Goal**: Search filters interview history by company or position.

**Independent Test**: `npx playwright test tests/e2e/interview-search-recovery.spec.ts --grep "filters sessions by company and position"`

### Tests for User Story 1

- [X] T005 [P] [US1] Add Playwright matching-search scenario in `tests/e2e/interview-search-recovery.spec.ts`

### Implementation for User Story 1

- [X] T006 [US1] Add stable search input selector and normalized query filtering in `src/pages/InterviewList.tsx`
- [X] T007 [US1] Verify company and position matching remains case-insensitive in `src/pages/InterviewList.tsx`

---

## Phase 4: User Story 2 - Recover from no search results (Priority: P1)

**Goal**: No-match search shows query-specific recovery and restores the full list when cleared.

**Independent Test**: `npx playwright test tests/e2e/interview-search-recovery.spec.ts --grep "clears a no-result search"`

### Tests for User Story 2

- [X] T008 [P] [US2] Add Playwright no-result clear-search scenario in `tests/e2e/interview-search-recovery.spec.ts`

### Implementation for User Story 2

- [X] T009 [US2] Add query-specific search empty state in `src/pages/InterviewList.tsx`
- [X] T010 [US2] Add clear-search action that restores all visible history records in `src/pages/InterviewList.tsx`

---

## Phase 5: User Story 3 - Preserve true empty history behavior (Priority: P2)

**Goal**: Users with no interview records still see first-interview guidance, not search recovery.

**Independent Test**: `npx playwright test tests/e2e/interview-search-recovery.spec.ts --grep "preserves true empty history"`

### Tests for User Story 3

- [X] T011 [P] [US3] Add Playwright true-empty-history scenario in `tests/e2e/interview-search-recovery.spec.ts`

### Implementation for User Story 3

- [X] T012 [US3] Add stable true empty-history selector without changing existing empty-history behavior in `src/pages/InterviewList.tsx`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate and document completion.

- [X] T013 Run `npm run typecheck`
- [X] T014 Run `npx playwright test tests/e2e/interview-search-recovery.spec.ts`
- [X] T015 Update `specs/009-interview-search-recovery/quickstart.md` if validation commands differ

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup completion.
- **US1 (Phase 3)**: Depends on foundational fixtures.
- **US2 (Phase 4)**: Depends on foundational fixtures and builds on the same search state.
- **US3 (Phase 5)**: Depends on foundational empty-history fixture.
- **Polish (Phase 6)**: Depends on US1, US2, and US3 completion.

## Parallel Opportunities

- T003 and T004 can be drafted together in the E2E file.
- T005, T008, and T011 can be written before implementation as failing tests.
- UI implementation tasks touch the same file and should be done sequentially.

## Implementation Strategy

1. Write E2E tests first and confirm missing recovery selectors fail.
2. Implement normalized query filtering and stable selectors.
3. Add query-specific no-results recovery while preserving true empty history.
4. Run focused E2E and typecheck.
5. Mark completed tasks in this file.
