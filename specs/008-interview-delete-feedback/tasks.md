# Tasks: Interview Delete Feedback

**Input**: Design documents from `/specs/008-interview-delete-feedback/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/interview-delete-ui.md](./contracts/interview-delete-ui.md), [quickstart.md](./quickstart.md)

**Tests**: Required by the feature specification and constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current feature context and existing files.

- [X] T001 Verify `.specify/feature.json` points to `specs/008-interview-delete-feedback`
- [X] T002 Confirm existing delete mutation and interview list files in `src/hooks/queries/useInterviewSessions.ts` and `src/pages/InterviewList.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create deterministic E2E fixtures used by all stories.

- [X] T003 [P] Create authenticated interview list route fixtures in `tests/e2e/interview-delete-feedback.spec.ts`
- [X] T004 [P] Add stable test coverage for cancel-without-side-effects in `tests/e2e/interview-delete-feedback.spec.ts`

**Checkpoint**: E2E harness can open `/interview` with deterministic interview session data.

---

## Phase 3: User Story 1 - Delete a history record (Priority: P1) MVP

**Goal**: A successful delete removes the selected interview card after confirmation.

**Independent Test**: `npx playwright test tests/e2e/interview-delete-feedback.spec.ts --grep "removes a session after confirmed delete"`

### Tests for User Story 1

- [X] T005 [P] [US1] Add Playwright success-delete scenario in `tests/e2e/interview-delete-feedback.spec.ts`

### Implementation for User Story 1

- [X] T006 [US1] Ensure confirm button exposes pending state and prevents duplicate submit in `src/pages/InterviewList.tsx`
- [X] T007 [US1] Verify successful delete closes the dialog and refreshes the visible list in `src/pages/InterviewList.tsx`

---

## Phase 4: User Story 2 - Recover from delete failure (Priority: P1)

**Goal**: A failed delete leaves context intact and shows retryable inline feedback.

**Independent Test**: `npx playwright test tests/e2e/interview-delete-feedback.spec.ts --grep "keeps the dialog open after delete failure"`

### Tests for User Story 2

- [X] T008 [P] [US2] Add Playwright failure-and-retry scenario in `tests/e2e/interview-delete-feedback.spec.ts`

### Implementation for User Story 2

- [X] T009 [US2] Add delete error state and inline error message in `src/pages/InterviewList.tsx`
- [X] T010 [US2] Clear delete error when retrying, cancelling, or selecting a new delete target in `src/pages/InterviewList.tsx`

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Validate and document completion.

- [X] T011 Run `npm run typecheck`
- [X] T012 Run `npx playwright test tests/e2e/interview-delete-feedback.spec.ts`
- [X] T013 Update `specs/008-interview-delete-feedback/quickstart.md` if validation commands differ

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup completion.
- **US1 (Phase 3)**: Depends on foundational fixtures.
- **US2 (Phase 4)**: Depends on foundational fixtures; can share the same UI state changes as US1.
- **Polish (Phase 5)**: Depends on US1 and US2 completion.

## Parallel Opportunities

- T003 and T004 can be drafted together in the E2E file.
- T005 and T008 can be written before implementation as failing tests.
- UI implementation tasks touch the same file and should be done sequentially.

## Implementation Strategy

1. Write E2E tests first and confirm they expose the missing failure-feedback behavior.
2. Implement minimal dialog error state and pending-state guards.
3. Run focused E2E and typecheck.
4. Mark completed tasks in this file.
