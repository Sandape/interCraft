# Implementation Plan: Resume Export Gateway

**Branch**: `[012-resume-export-gateway]` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-resume-export-gateway/spec.md`

## Summary

Connect the existing resume editor binary export UI to a working main backend route at `/api/v1/export/render`. The route validates render input, reuses the existing resume rendering module, returns downloadable binary responses, and gives the frontend structured error details so the export menu can remain open with actionable failure feedback.

## Technical Context

**Language/Version**: TypeScript 5.6 with React 18 and Vite; Python 3.12 with FastAPI

**Primary Dependencies**: Existing React export menu/client, FastAPI router, existing Playwright-based resume renderer

**Storage**: N/A; export is stateless and does not persist records

**Testing**: pytest contract tests, Vitest frontend API tests, Playwright E2E tests, curl against local backend

**Target Platform**: Local development web application and FastAPI backend

**Project Type**: Web application with SPA frontend and backend API

**Performance Goals**: Local PDF export completes within 10 seconds for a typical resume; validation errors return without invoking the renderer

**Constraints**: Keep scope limited to binary export gateway and feedback. Preserve existing Markdown export behavior. Avoid new dependencies.

**Scale/Scope**: One endpoint, one frontend client hardening, one E2E happy path, one E2E failure path.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | Reuses existing self-contained renderer module and keeps frontend client logic isolated in `src/api/export.ts`. |
| II. CLI Interface | PASS | Backend route remains curl-testable; renderer can still be exercised by Python tests without browser UI. |
| III. Test-First | PASS | Contract/API/E2E tests are tasks before implementation. |
| IV. Integration & Synchronization Testing | PASS | Includes backend contract, frontend client, curl, and browser E2E validation. |
| V. Observability | PASS | Route returns request IDs and logs render attempts/failures. |

## Project Structure

### Documentation (this feature)

```text
specs/012-resume-export-gateway/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- resume-export-api.md
`-- tasks.md
```

### Source Code (repository root)

```text
backend/
|-- app/api/v1/export.py
|-- app/api/v1/__init__.py
`-- tests/contract/test_resume_export_api.py

src/
|-- api/export.ts
`-- components/resume/export/ExportMenu.tsx

tests/
|-- unit/export-api.test.ts
`-- tests/e2e/resume-export-gateway.spec.ts
```

**Structure Decision**: Keep the gateway inside the existing FastAPI v1 router because the frontend already calls `/api/v1/export/render`. Keep renderer code in its existing module. Frontend behavior stays in the existing export client and export menu.

## Complexity Tracking

No constitution violations.
