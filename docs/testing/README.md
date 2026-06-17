# Testing Guide

This file is the canonical testing entry point. Requirement behavior is defined
in `specs/`; this guide only describes where tests live and how to run them.

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
| `src/**/*.test.ts(x)` | canonical | Frontend component, hook, repository, and utility tests. |
| `tests/unit/` | canonical | Frontend unit tests that are not colocated. |
| `backend/tests/` | canonical | Backend unit, integration, and contract tests. |

## E2E Policy

- The root `playwright.config.ts` points to `tests/e2e`.
- Keep feature E2E specs near the feature name, for example
  `tests/e2e/019-cross-module-linking.spec.ts`.
- Use `tests/e2e/fixtures/` or `tests/e2e/_fixtures/` for test assets.

## Current Round-1 Material

`docs/testing/round-1/` is retained because the active `020` feature uses its
defect catalog and summary as implementation evidence. Do not treat it as a
general historical reports folder; it is tied to the current fix workflow.

## Evidence Policy

- Generated screenshots, traces, logs, and manual verification records belong in
  `docs/evidence/` or a feature-specific evidence directory.
- Evidence proves behavior; it does not define requirements. Link evidence from
  requirement status tables when a requirement is marked `done`.
