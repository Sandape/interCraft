# Implementation Plan: Global Search Command Palette

**Branch**: `[011-global-search]` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-global-search/spec.md`

## Summary

The topbar advertises a global search capability (`搜索简历、面试记录、能力维度…` with a `⌘K` hint) that does nothing today. This feature delivers a real command palette: a backend aggregated search endpoint over `resume_branches`, `interview_sessions`, `ability_dimensions`, `help_faq`, and `resources`; a frontend palette component mounted in `AppShell`; a global `Ctrl/Cmd+K` shortcut; and full keyboard + click + state handling. Scope: 1 backend module, 1 frontend component, 1 E2E spec (4 tests). Out of scope: search history persistence, semantic ranking, mobile-specific layout.

## Technical Context

**Language/Version**: TypeScript 5.x (strict, frontend) + Python 3.12 (backend, existing)

**Primary Dependencies** (existing, no new deps):
- Frontend: React 18, Vite, TanStack Query 5, react-router-dom 6, Tailwind, lucide-react. The existing `apiClient` already supports `AbortSignal`, so no new dep for stale-request cancellation.
- Backend: FastAPI, SQLAlchemy 2 async, Pydantic v2, the existing `enforce_rate_limit` for `scope="business"`, the existing `db_session_user_dep` for RLS.

**Storage**: No new tables. Read-only aggregator over `resume_branches`, `interview_sessions`, `ability_dimensions`, `help_faq`, `resources`, and the static `DIMENSIONS_META_STATIC` dict in `app.modules.abilities.api`.

**Testing**: Vitest (unit) + Playwright (E2E). Backend has a contract test against the new endpoint; frontend has a vitest unit test for the debounce/abort hook; the E2E spec uses `page.route()` to mock the backend.

**Target Platform**: Modern Chromium (the existing Playwright config), localhost dev.

**Project Type**: Web application (existing — `frontend/` + `backend/`).

**Performance Goals**: < 1.5 s p95 from keystroke to results render, in the dev environment, with 1 user, ~50 records per type.

**Constraints**:
- No new tables or migrations.
- No new npm or pip packages.
- Reuse existing `enforce_rate_limit` (`scope="business"`) and RLS session.
- Backend response payload ≤ 25 items total (hard cap).
- Per-type cap = 5.
- Query truncated to 200 chars client-side.

**Scale/Scope**: Single user, ~5 record types, ~50 records per type per user, 1 endpoint, 1 component, 4 E2E tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle                              | Status | Notes |
|----------------------------------------|--------|-------|
| I. Library-First                       | ✅ Pass | The new `search` backend module and the `CommandPalette` frontend component are self-contained, expose a narrow API, and have a unit test target. |
| II. CLI Interface                      | ✅ Pass | The new module exposes a FastAPI endpoint; the endpoint can be curled directly. (No new CLI surface required for v1 — consistent with most other modules in the codebase.) |
| III. Test-First                        | ✅ Pass | Phase 2 of `tasks.md` writes the E2E spec and the unit test before any implementation code lands. |
| IV. Integration & Synchronization Testing | ✅ Pass | The E2E spec covers the full request/response path against a Playwright-routed backend. An RLS isolation test is part of the spec. |
| V. Observability                       | ✅ Pass | The endpoint emits a `took_ms` field on the response and uses the existing structured logger with `request_id` and `user_id` from the request state. No new metrics infra is required for v1. |
| Technology & Stack Constraints         | ✅ Pass | No new tech, no new frameworks. TypeScript strict, FastAPI, existing ORM. |
| Development Workflow                   | ✅ Pass | Branch naming follows `[###-feature-name]`. The PR will include the spec, plan, tasks, and tests. |

No violations. No `Complexity Tracking` entries required.

## Project Structure

### Documentation (this feature)

```text
specs/011-global-search/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── search-api.md    # Phase 1 output
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/
│   │   └── __init__.py        # MODIFIED: register search_router
│   └── modules/
│       └── search/            # NEW MODULE
│           ├── __init__.py
│           ├── router.py
│           ├── schemas.py
│           ├── service.py
│           └── tests/
│               └── test_search.py

src/
├── api/
│   └── search.ts              # NEW: typed client for /api/v1/search
├── components/layout/
│   ├── AppShell.tsx           # MODIFIED: mount CommandPalette + global shortcut
│   ├── Topbar.tsx             # MODIFIED: wire topbar input to open palette
│   └── CommandPalette.tsx     # NEW: palette UI
├── hooks/queries/
│   └── useGlobalSearch.ts     # NEW: debounce + abort + fetch
└── types/
    └── search.ts              # NEW: shared SearchResponse TS types

tests/e2e/
└── global-search.spec.ts      # NEW: 4 E2E tests
```

**Structure Decision**: This is a web application, so the existing 2-process layout (frontend in `src/`, backend in `backend/`) is reused. No new top-level directories.

## Complexity Tracking

> No Constitution Check violations — this section is empty.

## Phase Plan

### Phase 0 — Research ✅ done
All 8 design decisions are in [research.md](./research.md).

### Phase 1 — Design & Contracts ✅ done
- [data-model.md](./data-model.md) — response shape + client state machine
- [contracts/search-api.md](./contracts/search-api.md) — endpoint contract
- [quickstart.md](./quickstart.md) — manual + automated validation scenarios

### Phase 2 — Tasks (to be generated by `/speckit-tasks`)
Phases per tasks.md template:
- Phase 1: Setup (no infra; confirm prerequisites)
- Phase 2: Foundational (write E2E spec + unit test first — TDD)
- Phase 3: User Story 1 (open + type + click result, P1)
- Phase 4: User Story 2 (keyboard navigation, P2)
- Phase 5: User Story 3 (empty/no-results/loading/error, P3)
- Phase 6: User Story 4 (outside-click + shortcut toggle + public-page suppression, P3)
- Phase 7: Polish (typecheck + full e2e run)

## Open Questions

None. All three high-impact ambiguities (matching strategy, per-type cap, stale-request handling) are resolved in [research.md](./research.md) and recorded in the spec's `## Clarifications` section.
