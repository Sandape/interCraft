# Implementation Plan: 性能与可观测性增强

**Branch**: `022-perf-observability-enhancement` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-perf-observability-enhancement/spec.md`

## Summary

补齐 v1 在可观测性与性能方面的六项高/中严重度 gap：(1) LLM 日志通过 `X-Request-ID` 关联 HTTP 请求；(2) Resume 列表 N+1 查询通过聚合子查询修复；(3) `error_questions` 表新增 `(user_id, status, frequency, created_at) WHERE deleted_at IS NULL` 部分索引；(4) 前端路由 `React.lazy` + `Suspense` 懒加载；(5) Vite `manualChunks` 函数形式分 vendor 包；(6) Prometheus `/metrics` 补全 LLM quota / checkpointer / WS / ARQ 四类指标。技术方案：后端用 `contextvars.ContextVar` 注入 request_id，structlog `bind_contextvars` 自动关联；Resume 列表用 `selectinload` + 内存聚合或在 SQL 层用 `COUNT(*) OVER()` 窗口聚合；前端用 `React.lazy` 替换 eager import，`vite.config.ts` 加 `manualChunks` 函数；metrics 用 `prometheus_client` 已有的 registry，新增 6 个 Collector。零业务逻辑改动，零契约改动（除新增 `version_count` / `block_count` 响应字段）。

## Technical Context

**Language/Version**: Python 3.11 (backend) + TypeScript 5.x (frontend)

**Primary Dependencies**: FastAPI 0.110+, SQLAlchemy 2.x, Alembic, langgraph 0.2.x, langgraph-checkpoint-postgres 1.0.x, psycopg-pool 3.2+, structlog, prometheus_client; React 18, react-router-dom 6.x, @tanstack/react-query 5.x, Vite 5.x, TailwindCSS

**Storage**: PostgreSQL 15+

**Testing**: pytest (backend unit + integration), Vitest (frontend unit), Playwright (E2E round-1 + round-2)

**Target Platform**: Linux server (backend) + modern browser Chrome 90+/Firefox 88+/Safari 14+ (frontend)

**Project Type**: Web service (FastAPI) + SPA (React/Vite)

**Performance Goals**: Resume 列表 10 分支 P95 ≤ 300ms；errors 列表 500 条 P95 ≤ 200ms；登录页首屏 JS gzip ≤ 500KB；`/metrics` 响应 < 50ms

**Constraints**: 不改 API 契约（除新增 `version_count` / `block_count`）；不引入 OpenTelemetry；不升级 langgraph 主版本；既有 E2E 零回归

**Scale/Scope**: 5 个 agent (interview/error_coach/resume_optimize/ability_diagnose/general_coach) + 4 个 ARQ worker + 17 个前端页面

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | request_id 中间件 / N+1 修复 / index 迁移 / metrics collector 各自边界清晰，LLM client 继续走集中化客户端 |
| II. CLI Interface | ✅ Pass | 本 feature 是 web/observability 优化，不新增 CLI；既有 CLI 不受影响 |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | 每个 US 先写测试：request_id 关联用日志断言测试；N+1 用 SQL 计数测试；index 用 EXPLAIN 测试；lazy/manualChunks 用构建产物断言；metrics 用 `/metrics` 抓取测试 |
| IV. Integration & Synchronization Testing | ✅ Pass | request_id 跨 HTTP → LLM 调用链用集成测试覆盖；N+1 修复用真实 PostgreSQL 验证；metrics 端点用真实 scrape 验证 |
| V. Observability | ✅ Pass | 本 feature 直接是可观测性增强：request_id 关联 + 6 类新指标 + 结构化日志字段扩展 |

**Gate Result**: PASS — 无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/022-perf-observability-enhancement/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── request-id.md    # X-Request-ID header contract
│   ├── resume-branch-list.md  # N+1 修复后的响应契约
│   └── metrics.md       # /metrics 端点契约
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── middleware/
│   │   └── request_id.py        # 新增: X-Request-ID 中间件 + ContextVar
│   ├── modules/
│   │   ├── resume/
│   │   │   └── service.py        # 修改: 列表查询改聚合子查询
│   │   └── errors/
│   │       └── models.py         # 不改模型, 仅迁移加索引
│   ├── agents/
│   │   └── llm_client.py         # 修改: 日志读 ContextVar request_id
│   ├── observability/
│   │   ├── metrics.py            # 修改: 新增 6 类 Collector
│   │   └── logging.py            # 修改: structlog processor 注入 request_id
│   └── main.py                   # 修改: 注册 request_id 中间件
├── alembic/versions/
│   └── xxxx_add_error_questions_compound_index.py  # 新增
└── tests/
    ├── unit/
    │   ├── test_request_id_middleware.py  # 新增
    │   ├── test_llm_client_request_id.py  # 新增
    │   └── test_metrics_collectors.py     # 新增
    └── integration/
        ├── test_resume_branch_list_n_plus_1.py  # 新增
        └── test_error_questions_index.py        # 新增

frontend/
├── src/
│   ├── App.tsx                   # 修改: React.lazy + Suspense
│   └── pages/                    # 不改, 仅路由层 lazy
├── vite.config.ts                # 修改: manualChunks 函数
└── tests/
    └── unit/
        └── test_route_lazy.test.ts  # 新增 (可选, 构建产物断言)
```

**Structure Decision**: 严格遵循既有 backend/ + frontend/ 双项目结构。新增 `middleware/request_id.py` 和 `observability/metrics.py` 扩展，不改既有目录组织。

## Implementation Strategy

### Phase A — 后端可观测性基线 (US1 + US5)

**目标**: request_id 关联 + metrics 补全，是后续 Phase B/C/D 的可观测性前提。

1. TDD: 先写 `test_request_id_middleware.py` 断言 `X-Request-ID` header 读取/生成/响应注入。
2. 实现 `middleware/request_id.py`: `ContextVar` 存 request_id，FastAPI middleware 读取 `X-Request-ID` 或生成 UUID，注入响应头。
3. TDD: 先写 `test_llm_client_request_id.py` 断言 `llm.invoke` 日志含 `request_id` 字段。
4. 修改 `llm_client.py`: 日志从 ContextVar 读取 request_id，structlog `bind_contextvars` 自动注入。
5. TDD: 先写 `test_metrics_collectors.py` 断言 6 类新指标存在且类型正确。
6. 实现 `observability/metrics.py` 扩展: `llm_quota_exhausted_total` (Counter) / `llm_quota_available` (Gauge) / `checkpointer_reconnect_total` (Counter) / `ws_connections_active` (Gauge) / `arq_jobs_queued` (Gauge) / `arq_jobs_failed_total` (Counter)。
7. 集成测试: HTTP 请求 → 触发 LLM 调用 → grep 日志按 request_id 关联。

### Phase B — 后端性能优化 (US2 + US3)

**目标**: Resume N+1 修复 + errors 表索引。

1. TDD: 先写 `test_resume_branch_list_n_plus_1.py` 断言 10 分支查询 SQL 计数 ≤ 2。
2. 修改 `resume/service.py`: 列表查询改用 `selectinload(ResumeBranch.versions)` + `selectinload(ResumeVersion.blocks)` + 内存聚合，或 SQL 层 `COUNT(*) OVER()` 窗口聚合。响应增加 `version_count` / `block_count`。
3. TDD: 先写 `test_error_questions_index.py` 断言 `EXPLAIN` 输出含 `Index Scan` 而非 `Seq Scan`。
4. 生成 Alembic 迁移: `CREATE INDEX CONCURRENTLY idx_error_questions_user_status_freq_created ON error_questions (user_id, status, frequency, created_at) WHERE deleted_at IS NULL`。
5. 前端 `resume-branches` 类型定义扩展 `version_count` / `block_count`，移除逐分支 COUNT 请求。

### Phase C — 前端构建优化 (US4 + US6)

**目标**: 路由懒加载 + vendor 分包。

1. 修改 `src/App.tsx`: 所有非首屏页面（非 `/login`）改为 `React.lazy(() => import(...))`，包裹 `<Suspense fallback={<Skeleton/>}>`。
2. 修改 `vite.config.ts`: `build.rollupOptions.output.manualChunks` 函数形式，将 `react` / `react-dom` / `react-router-dom` / `@tanstack/react-query` 分入 `vendor`。
3. 构建产物断言: `npm run build` 后 `dist/assets/` 存在 `vendor-*.js`，体积 ≥ 40% 总 JS；登录页首屏 JS gzip ≤ 500KB。
4. 仅改业务代码（如 `Login.tsx`）重build，`vendor-*.js` hash 不变。

### Phase D — 跨切面验证 + 回归

**目标**: 既有 E2E 零回归 + SC 全部达成。

1. 跑 round-1 + round-2 E2E 套件，确认 21/21 通过。
2. 跑后端 88+ 单测 + 前端 vitest，确认无回归。
3. 验证 SC-001~007: request_id 覆盖率 100%、Resume P95 ≤ 300ms、errors P95 ≤ 200ms、首屏 ≤ 500KB、≥ 15 指标、vendor ≥ 40%、E2E 零回归。

## Complexity Tracking

> 无 Constitution Check 违规，本节为空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
