# Tasks: Error Book Completion

**Input**: Design documents from `/specs/016-error-book-completion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required by user request and constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current module boundaries and test entry points.

- [X] T001 Review existing error module, frontend page, hooks, repository, and E2E route files listed in specs/016-error-book-completion/plan.md
- [X] T002 Verify current worktree changes are not reverted or overwritten outside the error book scope

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add contract coverage for the missing recall action and UI runtime hazards before implementation.

- [X] T003 [P] Add failing backend integration tests for recall transitions, already-mastered recall conflict, deleted recall 404, and reset conflict in backend/tests/integration/test_error_questions_crud.py
- [X] T004 [P] Add failing frontend repository tests for recall client behavior and mock behavior in src/repositories/__tests__/ErrorQuestionRepository.test.ts
- [X] T005 [P] Add failing Playwright E2E scaffolding for normal and interrupted error book flows in tests/e2e/error-book-completion.spec.ts

**Checkpoint**: Tests describe required behavior before production code changes.

---

## Phase 3: User Story 1 - 记录并管理错题 (Priority: P1) MVP

**Goal**: Users can create, list, filter, search, and inspect readable error questions.

**Independent Test**: Create an error question from the page and verify it appears in list and detail; backend create/list/get tests pass.

### Tests for User Story 1

- [X] T006 [P] [US1] Ensure backend create/list validation assertions cover dimension, invalid input, and current-user scope in backend/tests/integration/test_error_questions_crud.py
- [X] T007 [P] [US1] Ensure frontend E2E creates a question, filters/searches it, and opens detail in tests/e2e/error-book-completion.spec.ts

### Implementation for User Story 1

- [X] T008 [US1] Fix ErrorQuestion frontend type shape and create payload support in src/repositories/ErrorQuestionRepository.ts
- [X] T009 [US1] Replace broken ErrorBook page text and remove invalid hook usage in src/pages/ErrorBook.tsx
- [X] T010 [US1] Add clear loading, empty, no-results, and create-error states in src/pages/ErrorBook.tsx

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - 复习推进与掌握状态 (Priority: P1)

**Goal**: Users can click “答对一次” to reduce frequency/status, then reset mastered questions.

**Independent Test**: Create a question, recall three times to mastered, reset to fresh/frequency=3.

### Tests for User Story 2

- [X] T011 [P] [US2] Add service-level recall assertions through backend integration tests in backend/tests/integration/test_error_questions_crud.py
- [X] T012 [P] [US2] Add frontend E2E assertions for recall-to-mastered and reset in tests/e2e/error-book-completion.spec.ts

### Implementation for User Story 2

- [X] T013 [US2] Implement recall business logic and timestamp handling in backend/app/modules/errors/service.py
- [X] T014 [US2] Implement recall repository persistence in backend/app/modules/errors/repository.py
- [X] T015 [US2] Expose POST /api/v1/error-questions/{id}/recall in backend/app/modules/errors/api.py
- [X] T016 [US2] Add recall client method and React Query mutation in src/repositories/ErrorQuestionRepository.ts and src/hooks/mutations/useErrorQuestionMutations.ts
- [X] T017 [US2] Wire detail action “答对一次” to recall mutation and update visible state in src/pages/ErrorBook.tsx

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - 删除、异常和重进恢复 (Priority: P2)

**Goal**: Delete, error feedback, and leave/re-enter recovery work reliably.

**Independent Test**: Delete hides a question; failed operations show error; create/recall persists across navigation.

### Tests for User Story 3

- [X] T018 [P] [US3] Add backend assertions for recall on deleted and cross-user questions in backend/tests/integration/test_error_questions_crud.py
- [X] T019 [P] [US3] Add E2E interrupted leave-and-return flow and invalid operation feedback in tests/e2e/error-book-completion.spec.ts

### Implementation for User Story 3

- [X] T020 [US3] Ensure soft-deleted questions are excluded from detail/list/recall/reset paths in backend/app/modules/errors/service.py
- [X] T021 [US3] Add page-level operation feedback and selected-item cleanup after delete/filter changes in src/pages/ErrorBook.tsx
- [X] T022 [US3] Keep Error Coach CTA visible only for frequency > 0 while preserving existing panel integration in src/pages/ErrorBook.tsx

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification and audit.

- [X] T023 Run backend focused tests from specs/016-error-book-completion/quickstart.md
- [X] T024 Run frontend repository tests and typecheck from specs/016-error-book-completion/quickstart.md
- [X] T025 Run backend curl smoke test against local server from specs/016-error-book-completion/quickstart.md
- [X] T026 Use in-app browser to visually inspect /error-book at desktop and narrow widths
- [X] T027 Use in-app browser to execute normal and interrupted E2E scenarios
- [X] T028 Perform code review across correctness, readability, architecture, security, performance, and verification
- [X] T029 Update tasks.md checkboxes to [X] for completed tasks

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 has no dependencies.
- Phase 2 depends on Phase 1 and blocks user story implementation.
- User Story 1 and User Story 2 both depend on Phase 2; implement US1 first because it repairs the page used by US2.
- User Story 3 depends on US1 and US2.
- Phase 6 depends on all selected user stories.

### Parallel Opportunities

- T003, T004, and T005 can be prepared in parallel.
- T006 and T007 can be prepared in parallel.
- T011 and T012 can be prepared in parallel.
- T018 and T019 can be prepared in parallel.

## Implementation Strategy

### MVP First

1. Add failing tests for recall and page workflow.
2. Repair create/list/detail page behavior.
3. Add recall endpoint and wire UI.
4. Validate create/list/detail/recall before delete/recovery polish.

### Incremental Delivery

1. Backend recall slice -> focused integration tests.
2. Frontend repository/mutation slice -> Vitest/typecheck.
3. ErrorBook UI slice -> browser visual check.
4. E2E and curl acceptance -> code audit.
