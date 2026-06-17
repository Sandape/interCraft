# Source Map

This map records where code actually lives today. Use it to avoid stale paths in
older specs and reports.

## Canonical Source Roots

| Area | Current Path | Notes |
|---|---|---|
| Frontend app | `src/` | React 18, Vite, TanStack Query, Zustand. |
| Frontend tests | `src/**/*.test.ts(x)`, `tests/unit/` | Vitest and Testing Library. |
| Canonical E2E tests | `tests/e2e/` | Root `playwright.config.ts` points here. |
| Backend app | `backend/app/` | FastAPI, SQLAlchemy, modules, agents, services. |
| Backend tests | `backend/tests/`, `backend/app/**/tests/` | Pytest unit, integration, contract tests. |
| API/repository layer | `src/api/`, `src/repositories/` | Frontend HTTP clients and local repository abstractions. |
| Shared frontend library | `src/lib/`, `src/hooks/`, `src/stores/`, `src/types/` | Shared utilities and state. |

## Non-Canonical Or Historical Paths

| Path | Status | Guidance |
|---|---|---|
| `frontend/src/` | removed legacy path | Old specs that mention `frontend/src` should be interpreted as `src/`. |
| Root screenshots and snapshots | removed historical evidence | New evidence belongs under `docs/evidence/` or feature-specific evidence folders. |

## Feature Area Map

| Domain | Backend | Frontend | Specs |
|---|---|---|---|
| Auth and sessions | `backend/app/modules/auth/`, `backend/app/modules/sessions/` | `src/pages/Login.tsx`, `src/pages/Register.tsx`, `src/stores/useAuthStore.ts` | `specs/001-intercraft-product-spec/` |
| Resumes | `backend/app/modules/resumes/`, `backend/app/modules/versions/` | `src/pages/ResumeList.tsx`, `src/pages/ResumeEditor.tsx`, `src/components/resume/` | `specs/001-intercraft-product-spec/`, `specs/002-resume-editor-enhancement/`, `specs/017-topbar-new-resume/` |
| Jobs | `backend/app/modules/jobs/` | `src/pages/Jobs.tsx`, `src/components/jobs/` | `specs/014-job-tracking/`, `specs/015-jobs-status-alignment/`, `specs/019-cross-module-linking/` |
| Interviews | `backend/app/modules/interviews/`, `backend/app/agents/interview/` | `src/pages/InterviewList.tsx`, `src/pages/InterviewLive.tsx`, `src/pages/InterviewReport.tsx`, `src/components/interview/` | `specs/003-phase4-interview-agent/`, `specs/019-cross-module-linking/` |
| Error Book | `backend/app/modules/errors/` | `src/pages/ErrorBook.tsx`, `src/components/error-book/`, `src/components/errors/` | `specs/016-error-book-completion/`, `specs/019-cross-module-linking/` |
| Ability Profile | `backend/app/modules/ability_profile/`, `backend/app/modules/abilities/` | `src/pages/AbilityProfile/`, `src/pages/AbilityProfile.tsx`, `src/pages/AbilityProfileDetail.tsx` | `specs/006-personal-ability-profile/` |
