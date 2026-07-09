# Implementation Plan: 求职训练指挥台（工作台首页）

**Branch**: `057-dashboard-home-optimize` (spec dir; current git branch may differ) | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/057-dashboard-home-optimize/spec.md`

## Summary

将登录默认工作台从「指标墙 + 装饰建议」升级为 **求职训练指挥台**：L0 今日面试与主 CTA、L1 简历/漏斗/单一下一步/准备包/继续、L2 趋势·能力·可读活动；配套用户隔离的 `dashboard-summary` 聚合与分层缓存。

技术方案（详见 [research.md](./research.md)）：

1. **BFF 摘要**：新增 `GET /api/v1/me/dashboard-summary`，一次返回 L0 + 约定 L1/L2 切片；服务端按 `tz`/`local_date` 过滤今日面试并渲染活动中文标题。
2. **前端收敛**：`Dashboard.tsx` 以 `useDashboardSummary` 为主数据源；退役 `useResumeBranches` / `useTasks` 今日待办 / 双建议栏；L0→L1→L2 渐进渲染 + `placeholderData`。
3. **缓存**：Redis `dashboard_summary:{user_id}:{local_date}`，短 TTL + 写路径失效；对齐现有 `card_renderer`/`drill_cache` 模式。
4. **Auth 不重挡**：修复 `useCurrentUser` refetch 时把已认证会话打回 `unknown`（承接 REQ-037 最小集）。
5. **漏斗**：在 summary 内 GROUP BY 重算，不依赖有缺陷的 `JobRepository.stats` 旧键。

P1 MVP = US1–US5；P2 = US6–US10 同 REQ 跟随。

## Technical Context

**Language/Version**: TypeScript (strict) + React 18 (frontend); Python 3.12 (backend)

**Primary Dependencies**:
- Frontend: Vite, TanStack Query, Zustand auth store, react-router-dom, existing UI (`Card`/`Button`/`Badge`)
- Backend: FastAPI, SQLAlchemy 2.0, Redis (`get_redis`), existing modules `jobs` / `resumes_v2` / `interviews` / `activities` / `ability_profile`
- No new product framework; optional thin `backend/app/modules/dashboard/` library

**Storage**: PostgreSQL (jobs.interview_time, resumes_v2, interview_sessions, activities); Redis for summary cache only

**Testing**:
- Backend: pytest contract/unit for summary schema, today-filter, activity labels, cache isolation/invalidation
- Frontend: Vitest for Dashboard L0/L1 empty/data fixtures + suggestion single-panel; Playwright E2E for today-interview / resume link / no event-code titles / mobile CTA
- Auth: unit/integration for `useCurrentUser` not reblocking

**Target Platform**: Web app (desktop + common mobile widths); local Windows/macOS + Linux CI

**Project Type**: Full-stack product increment on existing dashboard surface

**Performance Goals**:
- L0 interactive after login: progressive (shell + today list) without waiting for L2
- Summary p95 (warm cache): ≤ 150ms service-side target; cold path acceptable under existing API budgets
- Eliminate duplicate first-screen `interview-sessions` fetches
- Cache TTL L0: 60s; ability slice: 300s

**Constraints**:
- RLS / `app.user_id` sole user-data path
- Cache keys MUST include `user_id` (+ `local_date` for today domain)
- Default TZ `Asia/Shanghai` (align REQ-054); accept `tz` query param
- No job-recommendation Feed; no live LLM on homepage
- Do not break resume center / jobs / interview happy paths

**Scale/Scope**:
- 10 user stories (P1: US1–5; P2: US6–10)
- 32 FRs; primary touch: new dashboard module + `Dashboard.tsx` + auth refetch + mutation invalidation hooks
- Spec dir: `specs/057-dashboard-home-optimize/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | New `dashboard` (or `me_dashboard`) module owns summary aggregation + cache + activity label helpers; FE hooks under `src/hooks/queries` |
| II. CLI Interface | ✅ PASS | Optional `python -m app.modules.dashboard.cli dump-summary --user …` for local/CI fixture replay; pytest remains primary gate |
| III. Test-First | ✅ PASS | Contract tests for summary schema + label map before UI polish; E2E stories for L0 |
| IV. Integration Testing | ✅ PASS | Summary endpoint with seeded jobs/resumes/sessions; cache isolation test; AuthGuard reblock regression |
| V. Observability | ✅ PASS | Structured logs on summary build/cache hit-miss; optional counter `dashboard_summary_cache_hit` |

### Post-Design Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | See Project Structure — single dashboard module + FE page/hooks |
| II. CLI Interface | ✅ PASS | Documented in [contracts/cli.md](./contracts/cli.md) |
| III. Test-First | ✅ PASS | [quickstart.md](./quickstart.md) validation order |
| IV. Integration Testing | ✅ PASS | [contracts/dashboard-summary.md](./contracts/dashboard-summary.md) |
| V. Observability | ✅ PASS | Cache hit/miss + request_id in summary path |

## Project Structure

### Documentation (this feature)

```text
specs/057-dashboard-home-optimize/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dashboard-summary.md
│   ├── activity-labels.md
│   ├── cache-invalidation.md
│   ├── frontend-query.md
│   └── cli.md
├── checklists/requirements.md
├── requirements-status.md
└── tasks.md                 # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
backend/app/modules/dashboard/
├── __init__.py
├── api.py                   # GET /api/v1/me/dashboard-summary
├── service.py               # aggregate L0/L1/L2
├── schemas.py
├── activity_labels.py       # type → title_zh templates
├── cache.py                 # Redis get/set/delete
├── funnel.py                # status aggregation + awaiting_feedback rule
└── cli.py                   # dump-summary for fixtures

backend/tests/
├── contract/test_dashboard_summary_schema.py
├── unit/test_activity_labels.py
├── unit/test_dashboard_funnel.py
└── integration/test_dashboard_summary.py

src/pages/Dashboard.tsx      # command-center layout
src/hooks/queries/useDashboardSummary.ts
src/hooks/useDashboardSuggestions.ts   # consume summary.next_action OR thin wrapper
src/hooks/queries/useCurrentUser.ts    # stop reblocking on refetch
src/lib/activityLabels.ts              # FE fallback mirror (optional if BE always labels)

# Mutation onSuccess sites (invalidate DASHBOARD_SUMMARY_KEY):
# jobs / resumes_v2 / interview-sessions / activities writers
```

**Structure Decision**: Full-stack web app — thin new backend `dashboard` module + existing `src/pages/Dashboard.tsx` rewrite against one summary query. No separate frontend package.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New BFF summary endpoint vs pure FE fan-out | Spec requires server today-filter, Chinese activity titles, funnel recompute, cache | FE-only still needs 8+ calls, cannot fix JobRepository.stats, duplicates sessions, weak cache coherency |
| Redis summary cache | FR-024～027 freshness + SC-006 | Relying only on TanStack cache fails cross-tab/device and does not reduce BE load on login storms |
