# Tasks: Resume Export Gateway

**Input**: Design documents from `/specs/012-resume-export-gateway/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required by specification and constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup

**Purpose**: Confirm existing export surfaces and active feature context.

- [X] T001 Verify existing frontend export menu/client and backend renderer paths in `src/components/resume/export/ExportMenu.tsx`, `src/api/export.ts`, and `backend/src/services/pdf_renderer/`

---

## Phase 2: Foundational

**Purpose**: Backend gateway contract before UI behavior.

- [X] T002 [P] Write backend contract tests for `/api/v1/export/render` success, validation errors, and renderer failure in `backend/tests/contract/test_resume_export_api.py`
- [X] T003 [P] Write frontend export API tests for filename parsing and structured error messages in `tests/unit/export-api.test.ts`

---

## Phase 3: User Story 1 - Download Rendered Resume (Priority: P1) MVP

**Goal**: Users can download binary PDF/PNG/JPEG exports from the visible editor export menu.

**Independent Test**: Seed a resume, choose PDF export, and verify a binary download is produced.

### Tests for User Story 1

- [X] T004 [US1] Run T002 and confirm the backend route tests fail before implementation
- [X] T005 [US1] Run T003 and confirm the frontend client tests fail before implementation

### Implementation for User Story 1

- [X] T006 [US1] Implement main export router in `backend/app/api/v1/export.py`
- [X] T007 [US1] Mount export router in `backend/app/api/v1/__init__.py`
- [X] T008 [US1] Harden filename and error parsing in `src/api/export.ts`
- [X] T009 [US1] Add stable export menu selectors in `src/components/resume/export/ExportMenu.tsx`

**Checkpoint**: Backend and frontend client tests pass.

---

## Phase 4: User Story 2 - See Export Failure Feedback (Priority: P2)

**Goal**: Rendering failures keep the export menu open with useful error feedback.

**Independent Test**: Force a render failure and verify the export menu displays an inline error.

### Tests for User Story 2

- [X] T010 [P] [US2] Write Playwright E2E for PDF download success and forced render failure in `tests/e2e/resume-export-gateway.spec.ts`

### Implementation for User Story 2

- [X] T011 [US2] Ensure `ExportMenu` keeps the menu open and displays `data-testid="export-error-message"` on failure in `src/components/resume/export/ExportMenu.tsx`

**Checkpoint**: E2E success and failure paths pass.

---

## Phase 5: Polish & Validation

- [X] T012 Run `npm run typecheck`
- [X] T013 Run `cd backend && uv run pytest tests/contract/test_resume_export_api.py -q`
- [X] T014 Run `npm run test -- tests/unit/export-api.test.ts`
- [X] T015 Run `npx playwright test tests/e2e/resume-export-gateway.spec.ts --workers=1`
- [X] T016 Validate backend curl success and error cases against local server
- [X] T017 Validate visible UI and E2E behavior with the in-app Browser
- [X] T018 Perform code review against correctness, readability, architecture, security, performance, and verification gates

---

## Dependencies & Execution Order

- T001 before implementation.
- T002 and T003 before T006-T009.
- T010 before final UI validation.
- T012-T018 after implementation.

## Parallel Opportunities

- T002 and T003 can run in parallel.
- T006/T007 are backend-only; T008/T009 are frontend-only after tests exist.
- Validation commands can run independently except where they require live servers.

## Implementation Strategy

1. Test backend and frontend contracts first.
2. Add the narrow backend route and frontend parsing/selectors.
3. Add E2E success/failure tests.
4. Run automated validation, curl validation, browser validation, and code review.
