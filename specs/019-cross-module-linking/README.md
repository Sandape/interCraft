# 019 Cross-Module Linking

Status: `active`

Source of truth: [spec.md](./spec.md)

This is the current SpecKit feature from `.specify/feature.json`. It connects
Jobs, Resume Branches, Interview Sessions, Error Book, and Ability Profile
without rewriting the internal logic of those modules.

## Implementation Context

| Area | Link |
|---|---|
| Source of truth | [spec.md](./spec.md) |
| Implementation plan | [plan.md](./plan.md) |
| Tasks | [tasks.md](./tasks.md) |
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Requirement status | [requirements-status.md](./requirements-status.md) |

## Contracts

- [jobs-fields.md](./contracts/jobs-fields.md)
- [interview-job-id.md](./contracts/interview-job-id.md)
- [error-questions-source.md](./contracts/error-questions-source.md)
- [requirements-md-prompt.md](./contracts/requirements-md-prompt.md)

## Related Code

| Subsystem | Current Paths |
|---|---|
| Jobs backend | `backend/app/modules/jobs/` |
| Interview backend | `backend/app/modules/interviews/`, `backend/app/agents/interview/` |
| Error Book backend | `backend/app/modules/errors/` |
| Resume branches backend | `backend/app/modules/resumes/` |
| Frontend API and repositories | `src/api/`, `src/repositories/` |
| Jobs UI | `src/pages/Jobs.tsx`, `src/components/jobs/` |
| Resume UI | `src/pages/ResumeList.tsx`, `src/pages/ResumeEditor.tsx`, `src/components/resume/` |
| Interview UI | `src/pages/InterviewList.tsx`, `src/pages/InterviewLive.tsx`, `src/pages/InterviewReport.tsx` |
| Error Book UI | `src/pages/ErrorBook.tsx`, `src/components/error-book/`, `src/components/errors/` |

## Related Tests

- Canonical E2E: `tests/e2e/019-cross-module-linking.spec.ts`
- Legacy/root E2E copy: `e2e/019-cross-module-linking.spec.ts`
- Backend tests added for 019 live under `backend/tests/unit/` and
  `backend/tests/integration/`.

## Do Not Use As Source

- `docs/modules/*` for implementation decisions.
- Old Phase 1-4 testing reports as requirements.
- Any `frontend/src` paths in old generated plans. The current frontend root is
  `src/`; see [docs/architecture/source-map.md](../../docs/architecture/source-map.md).

