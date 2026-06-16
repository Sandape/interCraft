# Tasks: Interview Resume Guardrails

**Input**: Design documents from `specs/007-interview-resume-guardrails/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/resume-ui.md](./contracts/resume-ui.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED by Constitution III and the feature request. Browser E2E tasks come before implementation tasks.

## Phase 1: Setup

- [x] T001 Verify `.specify/feature.json` points to `specs/007-interview-resume-guardrails`
- [x] T002 Confirm existing interview live/list source files in `src/pages/InterviewLive.tsx` and `src/pages/InterviewList.tsx`

## Phase 2: Foundational Test Coverage

- [x] T003 [P] [US3] Add Playwright E2E normal completion scenario in `tests/e2e/interview-resume-guardrails.spec.ts`
- [x] T004 [P] [US1] Add Playwright E2E leave-and-resume scenario in `tests/e2e/interview-resume-guardrails.spec.ts`
- [x] T005 [P] [US2] Add Playwright E2E resume failure scenario in `tests/e2e/interview-resume-guardrails.spec.ts`

## Phase 3: User Story 1 - Resume an In-Progress Interview (P1)

**Goal**: Re-entering an active interview shows restored continuity and allows the next answer.

**Independent Test**: `npx playwright test tests/e2e/interview-resume-guardrails.spec.ts --grep "resumes an in-progress interview"`

- [x] T006 [US1] Add stable restored answer selectors and resume summary in `src/pages/InterviewLive.tsx`
- [x] T007 [US1] Normalize restored questions/scores to avoid duplicate rendering in `src/pages/InterviewLive.tsx`
- [x] T008 [US1] Ensure next answer sequence number is initialized from restored user answers in `src/pages/InterviewLive.tsx`
- [x] T009 [US1] Add stable session-card selector and session id attribute in `src/pages/InterviewList.tsx`

## Phase 4: User Story 2 - Recover from Resume Load Failure (P1)

**Goal**: Resume load failure shows a retryable error state and never falls through to new setup.

**Independent Test**: `npx playwright test tests/e2e/interview-resume-guardrails.spec.ts --grep "shows a retryable resume error"`

- [x] T010 [US2] Add `data-testid="resume-error-state"` wrapper in `src/pages/InterviewLive.tsx`
- [x] T011 [US2] Add stable retry and return selectors in `src/pages/InterviewLive.tsx`
- [x] T012 [US2] Verify setup controls are not rendered in resume error state in `src/pages/InterviewLive.tsx`

## Phase 5: User Story 3 - Verify Full Interview Continuity (P2)

**Goal**: Focused E2E covers normal, resume success, and resume failure paths.

**Independent Test**: `npx playwright test tests/e2e/interview-resume-guardrails.spec.ts`

- [x] T013 [US3] Wire deterministic network route fixtures for interview list, session lookup, resume, and WebSocket-neutral behavior in `tests/e2e/interview-resume-guardrails.spec.ts`
- [x] T014 [US3] Assert no duplicate session creation during resume in `tests/e2e/interview-resume-guardrails.spec.ts`
- [x] T015 [US3] Capture screenshots for success and failure browser states under `test-results/interview-resume-guardrails/`

## Phase 6: Polish & Validation

- [x] T016 Run `npm run typecheck`
- [x] T017 Run `npm test -- --runInBand` or the closest supported focused unit command if needed
- [x] T018 Run focused Playwright suite from `specs/007-interview-resume-guardrails/quickstart.md`
- [x] T019 Update this `tasks.md` marking completed items
- [x] T020 Update automation memory at `$CODEX_HOME/automations/sdd/memory.md`

## Dependencies & Execution Order

- Phase 1 must finish before implementation.
- Phase 2 tests should be written before source changes.
- US1 and US2 source changes can be made together because they touch the same file and must be sequenced carefully.
- Phase 5 validation depends on US1 and US2 implementation.

## Parallel Opportunities

- T003, T004, and T005 can be drafted together but should be committed as one focused E2E file.
- T009 can be implemented independently from `InterviewLive.tsx` changes.

## Implementation Strategy

1. Add the focused E2E file first.
2. Implement stable UI selectors and restore summary.
3. Implement error-state selectors.
4. Run typecheck and focused browser tests.
5. Update task checkboxes and automation memory.
