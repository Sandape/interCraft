# Implementation Plan: Jobs Status Alignment

**Branch**: `015-jobs-status-alignment` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-jobs-status-alignment/spec.md`

## Summary

Fix the Jobs page so it speaks the backend's actual `JobStatus` vocabulary. The current UI hard-codes tabs for `screening` and `interview` (statuses that do not exist in `app.domain.enums.JobStatus`) and posts a `screening → interview` transition that the backend rejects with HTTP 409. Stats also lump `withdrawn` into `rejected`. The fix exposes a thin new endpoint `GET /api/v1/jobs/transitions` that returns the canonical `JOB_TRANSITIONS` graph, then rebuilds the Jobs page so its status tabs, row-level status popover, and 5 stat tiles are all derived from that single response. Terminal moves (`rejected`, `withdrawn`) prompt a confirm modal; a 409 from the backend surfaces an inline error with a retry affordance rather than silently rolling the status back.

## Technical Context

**Language/Version**: TypeScript 5.6 strict mode, React 18, Vite 5 (frontend); Python 3.11, FastAPI 0.115, SQLAlchemy 2.0 async (backend)

**Primary Dependencies** (existing, no new packages):
- Frontend: TanStack Query 5, lucide-react, react-router-dom 6, react (existing) — no new deps
- Backend: `app.domain.enums.JOB_TRANSITIONS`, `app.modules.jobs.api.router` (extend), `app.modules.jobs.schemas` (add one schema)
- E2E: Playwright with `page.route()` to mock the new endpoint and force 409 responses

**Storage**: No new tables. The new endpoint is a static read of the in-process `JOB_TRANSITIONS` dict. Existing `jobs` table is the source of truth for per-user counts and rows.

**Testing**: pytest (backend unit) + Vitest (frontend hook smoke) + Playwright (E2E)

**Target Platform**: Vite dev server (frontend) + FastAPI uvicorn (backend); modern desktop browser. Redis 7 reachable on `localhost:6379` and the existing online Postgres instance (per `CLAUDE.md` local-env notes).

**Project Type**: Web application (full-stack — frontend + backend)

**Performance Goals**: `GET /api/v1/jobs/transitions` returns in < 5 ms (pure in-process dict). Frontend fetches it once per session (TanStack Query `staleTime: Infinity`). The popover must open in < 100 ms after hover/click on the row's action button.

**Constraints**:
- No new npm or pip packages
- No new database tables or migrations
- No new URLs or URL state for tabs
- The new endpoint is auth-protected and idempotent (read-only)
- The frontend MUST NOT hard-code `JOB_TRANSITIONS` — it must fetch the graph
- The fallback copy (when the fetch fails) is small and explicitly marked stale via a banner
- The `screening` and `interview` strings MUST be removed from `src/components/jobs/StatusBadge.tsx` and `src/pages/Jobs.tsx`
- 5 stat tiles in this order: `总申请`, `进行中` (Active), `Offer`, `已拒绝`, `已撤回`

**Scale/Scope**: 1 backend endpoint (GET only), 1 frontend hook, 1 frontend component refactor (`Jobs.tsx`), 2 new UI components (`StatusPopover`, `TerminalConfirmModal`), 1 status badge update, 1 E2E spec.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Library-First | The new `jobs/transitions` endpoint lives inside the existing `app.modules.jobs.api` module — same module that already owns `list_jobs`, `update_job_status`, etc. No cross-module imports. The frontend change is local to `src/pages/Jobs.tsx` + one new hook under `src/hooks/queries/`. | PASS |
| II. CLI Interface | The new endpoint is curl-friendly: `GET /api/v1/jobs/transitions` with the same `Authorization: Bearer` header every other Jobs endpoint accepts. The shape is documented in `contracts/jobs-transitions.md`. Existing CLI at `app.modules.jobs.cli` keeps working unchanged. | PASS |
| III. Test-First | The Playwright E2E spec `tests/e2e/jobs-status-alignment.spec.ts` is written first with 3 failing tests (happy path, 409 retry, no-phantom-tab). The backend has a small pytest covering the endpoint shape and 401 behavior. Frontend hook has a vitest unit test for the cache-fallback path. | PASS |
| IV. Integration & Synchronization Testing | The E2E spec exercises the full request/response path against a Playwright-routed backend. The failure path is reproducible by `page.route()` returning a 409 to the `PATCH /jobs/{id}/status` call. RLS is not engaged (the endpoint is static, no user data). | PASS |
| V. Observability | The backend endpoint emits a structured `jobs.transitions.fetched` log with `request_id` and `user_id`. The frontend mutation emits `jobs.status_update.failed` with the `to` value and the backend error code. No PII beyond user_id. | PASS |

No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/015-jobs-status-alignment/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── jobs-transitions.md  # Phase 1 output
├── checklists/
│   └── requirements.md  # Quality checklist (16/16 passing)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
└── app/
    └── modules/jobs/
        ├── api.py                   # MODIFIED: register GET /api/v1/jobs/transitions
        ├── schemas.py               # MODIFIED: add TransitionsOut, TransitionEdge
        └── service.py               # MODIFIED: add get_transitions() helper

src/
├── api/jobs.ts                      # MODIFIED: add getJobTransitions() typed client
├── hooks/queries/
│   ├── useJobTransitions.ts         # NEW: TanStack Query hook, staleTime: Infinity, fallback
│   └── useJobs.ts                   # unchanged
├── components/jobs/
│   ├── StatusBadge.tsx              # MODIFIED: replace screening/interview with test/oa/hr; keep "未知" fallback
│   ├── StatusPopover.tsx            # NEW: row-level status popover (MoreHorizontal trigger, derived menu, terminal-confirm)
│   └── TerminalConfirmModal.tsx     # NEW: confirm modal for rejected/withdrawn
├── pages/Jobs.tsx                   # MODIFIED: tabs from useJobTransitions, count badges, 5 stat tiles, status popover, inline error
├── types/jobs.ts                    # NEW: shared TS types for the transitions response
└── repositories/__tests__/JobRepository.test.ts  # MODIFIED: switch fixture counts to real backend statuses

tests/
└── e2e/
    └── jobs-status-alignment.spec.ts  # NEW: 3 E2E scenarios (happy path, 409 retry, phantom tabs gone)
```

**Structure Decision**: Web application (Option 2) — both `backend/` and `src/` are touched. The new pieces are minimal and stay inside the existing `jobs` module / `pages` directory.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | -          | - |

No entries. The new endpoint is a static read of an existing in-process dict; the UI is a localized refactor.

## Re-evaluation after Phase 1 design

Phase 1 制品(`research.md` / `data-model.md` / `contracts/jobs-transitions.md` / `quickstart.md`)未引入新依赖、新数据库表、新跨模块耦合,5 条 Constitution 原则**全部维持 PASS**:

- **I. Library-First** — 新端点注册在 `app.modules.jobs.api`,新增 `useJobTransitions` 位于 `src/hooks/queries/`,均未跨界。
- **II. CLI Interface** — 端点 curl-friendly,`quickstart.md §1` 给出验证命令;既有 `app.modules.jobs.cli` 不受影响。
- **III. Test-First** — `quickstart.md §5` 与 §6 列出先行的 Playwright E2E + 单元测试入口;`tasks.md` 中 P1 / P2 任务已拆分。
- **IV. Integration & Synchronization Testing** — 失败路径用 Playwright `page.route()` 真实拦截,非 mock;新端点是静态读,无 RLS 风险。
- **V. Observability** — 后端 `jobs.transitions.fetched` / 前端 `jobs.status_update.failed` 结构化日志,`request_id` + `user_id` 关联,无新增 PII。

无未决议题,Phase 1 完结;可直接进入 `/speckit-tasks` 或按 tasks.md 中已存在的 T 编号开干。
