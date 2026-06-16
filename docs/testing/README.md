# Testing Guide

This file is the canonical testing entry point. Older test plans and reports in
this directory are historical evidence unless explicitly linked from a feature
spec or this guide.

## Commands

| Purpose | Command |
|---|---|
| Frontend unit tests | `npm run test` |
| Frontend type check | `npm run typecheck` |
| Frontend build | `npm run build` |
| Canonical E2E tests | `npm run e2e` |
| List canonical E2E tests | `npm run e2e -- --list` |
| Backend tests | `cd backend && uv run pytest -q` |
| Backend contract tests | `cd backend && uv run pytest tests/contract -q` |

## Test Roots

| Root | Status | Purpose |
|---|---|---|
| `tests/e2e/` | canonical | Playwright E2E specs. Add new E2E tests here. |
| `e2e/` | legacy | Migration source only. Do not add new tests here. |
| `src/**/*.test.ts(x)` | canonical | Frontend component, hook, repository, and utility tests. |
| `tests/unit/` | canonical | Frontend unit tests that are not colocated. |
| `backend/tests/` | canonical | Backend unit, integration, and contract tests. |
| `docs/test/e2e/` | legacy example | Documentation example only, not a runnable test root. |

## E2E Policy

- The root `playwright.config.ts` points to `tests/e2e`.
- Keep feature E2E specs near the feature name, for example
  `tests/e2e/019-cross-module-linking.spec.ts`.
- Use `tests/e2e/fixtures/` or `tests/e2e/_fixtures/` for test assets.
- Root `e2e/` remains only until duplicate or older tests are audited and moved.

## Evidence Policy

- Generated screenshots, traces, logs, and manual verification records belong in
  `docs/evidence/` or a feature-specific evidence directory.
- Evidence proves behavior; it does not define requirements. Link evidence from
  requirement status tables when a requirement is marked `done`.

## Historical Reports

The following files remain useful for background, but do not define the current
test strategy:

- [test-plan-phase1-4.md](./test-plan-phase1-4.md)
- [test-report-phase1-4.md](./test-report-phase1-4.md)
- [test-report-phase1-4-zh.md](./test-report-phase1-4-zh.md)
- [issues-summary-phase1-4.md](./issues-summary-phase1-4.md)
- [issues-summary-phase1-4-zh.md](./issues-summary-phase1-4-zh.md)
- [optimization-suggestions-phase1-4.md](./optimization-suggestions-phase1-4.md)
- [ui-ux-evaluation.md](./ui-ux-evaluation.md)

