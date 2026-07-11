# InterCraft Agent Context

This file is the always-loaded routing layer for AI coding agents. Keep it short
and point agents to the canonical source for the current task.

<!-- SPECKIT START -->
Current SpecKit plan: `specs/061-ai-agent-production/plan.md`.
<!-- SPECKIT END -->

## Canonical Navigation

1. Current active SpecKit feature: read `.specify/feature.json`.
2. Requirements index: read `specs/README.md`.
3. Active feature context: read that feature's `README.md`, then only the
   relevant `spec.md`, `contracts/`, `tasks.md`, and `requirements-status.md`.
4. Test guidance: read `docs/testing/README.md`.
5. Source layout: read `docs/architecture/source-map.md`.

## Project Shape

- Frontend: `src/` (React 18, Vite, TypeScript, TanStack Query, Zustand).
- Backend: `backend/app/` (FastAPI, SQLAlchemy 2.0, Alembic, Redis/ARQ).
- Canonical E2E tests: `tests/e2e/`.
- Generated or manual evidence: `docs/evidence/` and feature-specific evidence
  folders.

If an old spec or plan mentions `frontend/src`, interpret that as the current
frontend root `src/` unless the source map says otherwise.

## Commands

| Purpose | Command |
|---|---|
| Frontend dev server | `npm run dev` |
| Frontend unit tests | `npm run test` |
| Frontend type check | `npm run typecheck` |
| Frontend build | `npm run build` |
| Canonical E2E tests | `npm run e2e` |
| List canonical E2E tests | `npm run e2e -- --list` |
| Backend tests | `cd backend && uv run pytest -q` |
| Backend migrations | `cd backend && uv run alembic upgrade head` |

## Requirement Status Rules

- Feature-level status is tracked in `specs/README.md`.
- Requirement-level status is tracked in feature `requirements-status.md` files
  for active or important features.
- Mark a requirement `done` only when implementation and verification evidence
  are both present.
- Use `in_progress` when code exists but validation is still pending.
- Use `legacy` or `superseded` for historical documents that are no longer
  implementation sources.

## Working Rules

- Do not move `specs/*` directories just to separate done and unfinished work;
  SpecKit depends on stable paths.
- Legacy docs and unreferenced evidence were intentionally removed after the
  SpecKit documentation system became canonical. Use git history only when old
  context is truly needed.
- Treat the current dirty worktree as user/ongoing work. Do not revert changes
  you did not make.
- Use the current codebase as the source of path truth. Older generated plans
  may contain stale paths.
- PowerShell may display UTF-8 Chinese as mojibake. If Chinese docs look
  corrupted in terminal output, re-read with Node or another UTF-8-safe reader
  before deciding the file is damaged.
