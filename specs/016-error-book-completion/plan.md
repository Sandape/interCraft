# Implementation Plan: Error Book Completion

**Branch**: `[016-error-book-completion]` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-error-book-completion/spec.md`

## Summary

Complete the existing error book module as a production-ready learning loop: preserve current CRUD endpoints, add the missing recall action, enforce frequency/status transitions consistently, repair the ErrorBook page text and runtime behavior, and verify normal plus interrupted user journeys through backend, frontend, curl, and browser E2E checks.

## Technical Context

**Language/Version**: Python 3.11 backend; TypeScript strict frontend

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Pydantic v2, React 18, React Query, Vite, TailwindCSS, Playwright

**Storage**: PostgreSQL via existing SQLAlchemy models and migrations

**Testing**: pytest/httpx ASGI integration tests; Vitest for frontend repository behavior; Playwright/browser checks for E2E

**Target Platform**: Local web application with FastAPI backend and Vite frontend

**Project Type**: Full-stack web application

**Performance Goals**: Error book list and single-item interactions should feel immediate for ordinary page sizes; list endpoints remain bounded by server-side limit <= 50.

**Constraints**: Preserve existing `/api/v1/error-questions` contract compatibility; no new dependency unless existing stack cannot solve it; user-owned data must remain scoped to the authenticated user.

**Scale/Scope**: One module: backend `backend/app/modules/errors`, frontend `src/pages/ErrorBook.tsx` and repository/hooks, focused tests and E2E.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | Changes stay inside the existing self-contained errors module and frontend repository/hooks/page surfaces. |
| II. CLI Interface | PASS | Existing backend package CLI remains unchanged; validation is available through pytest/curl and app scripts. |
| III. Test-First | PASS | Tasks require failing backend/frontend/E2E tests before implementation. |
| IV. Integration & Synchronization Testing | PASS | Integration tests, curl validation, and browser E2E cover API and UI boundaries plus leave/re-enter recovery. |
| V. Observability | PASS | No new background process; user-safe error handling and existing request correlation remain in place. |

## Project Structure

### Documentation (this feature)

```text
specs/016-error-book-completion/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- error-book-api.md
|   `-- error-book-ui.md
`-- tasks.md
```

### Source Code (repository root)

```text
backend/
|-- app/modules/errors/
|   |-- api.py
|   |-- repository.py
|   |-- schemas.py
|   `-- service.py
`-- tests/integration/
    `-- test_error_questions_crud.py

src/
|-- pages/
|   `-- ErrorBook.tsx
|-- repositories/
|   |-- ErrorQuestionRepository.ts
|   `-- __tests__/ErrorQuestionRepository.test.ts
`-- hooks/
    |-- queries/useErrorQuestions.ts
    `-- mutations/useErrorQuestionMutations.ts

tests/e2e/
`-- error-book-completion.spec.ts
```

**Structure Decision**: Use the existing full-stack layout and module boundaries. The backend error module remains the API/service/repository owner, and the frontend keeps server-state operations in repository + React Query hooks while the page remains a presentation/workflow surface.

## Complexity Tracking

No constitution violations.

## Phase 0: Research

See [research.md](./research.md).

## Phase 1: Design & Contracts

- Data model: [data-model.md](./data-model.md)
- API contract: [contracts/error-book-api.md](./contracts/error-book-api.md)
- UI contract: [contracts/error-book-ui.md](./contracts/error-book-ui.md)
- Validation guide: [quickstart.md](./quickstart.md)

## Post-Design Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | No cross-module ownership drift. |
| II. CLI Interface | PASS | Existing script and test surfaces are sufficient. |
| III. Test-First | PASS | Contract/integration/repository/E2E tests are explicit tasks before code. |
| IV. Integration & Synchronization Testing | PASS | End-to-end normal and interrupted flows are required. |
| V. Observability | PASS | Errors remain user-safe and diagnosable through HTTP status and response body. |
