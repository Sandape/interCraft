# Research: 性能与可观测性增强

**Date**: 2026-06-22

## Research Questions

### RQ-001: request_id 在异步上下文中如何传递?

**Decision**: 使用 `contextvars.ContextVar` + structlog `bind_contextvars` / `clear_contextvars`。

**Rationale**:
- `contextvars` 是 Python 3.7+ 标准库，asyncio 安全，FastAPI/Starlette middleware 中是业界标准做法。
- `threading.local` 在 async 场景下会串号（多个请求共享同一 thread）。
- structlog 原生支持 `bind_contextvars` / `clear_contextvars`，无需自定义 processor。
- ARQ worker 上下文无 HTTP request，需在 `on_job_start` 钩子中显式 `bind_contextvars(request_id=job_id)`。

**Alternatives considered**:
- OpenTelemetry context propagation — 重量级，spec 明确不引入 OTel。
- 显式传参给每个 LLM 调用 — 侵入性大，5 个 graph + 多个 service 都要改。
- structlog `BoundLogger` 手动 bind — 容易漏 bind，ContextVar 自动注入更可靠。

### RQ-002: Resume 列表 N+1 修复用 selectinload 还是窗口函数?

**Decision**: `selectinload` + 内存聚合。

**Rationale**:
- SQLAlchemy 2.x `selectinload` 会用 `WHERE id IN (...)` 二次查询，对 10 分支 × 3 版本 × 5 块 = 150 行的小数据集，2 次 SQL（1 次分支 + 1 次版本+块 join）比窗口函数更易读。
- 窗口函数 `COUNT(*) OVER(PARTITION BY branch_id)` 需要手写 SQL，与 SQLAlchemy ORM 风格不一致。
- 内存聚合 `len(branch.versions)` / `sum(len(v.blocks) for v in branch.versions)` 简单直观，对小数据集零性能差异。

**Alternatives considered**:
- `subqueryload` — 一次 SQL 但用 LEFT JOIN，笛卡尔积膨胀，块数 × 版本数 行。
- 手写 `SELECT b.*, COUNT(v.*) OVER(), COUNT(bl.*) OVER() FROM ...` — 复杂且 ORM 不友好。
- 前端独立 batch COUNT 接口 — 增加往返，与 SC-002「SQL ≤ 2 次」冲突。

### RQ-003: error_questions 部分索引 vs 全索引?

**Decision**: 部分索引 `(user_id, status, frequency, created_at) WHERE deleted_at IS NULL`。

**Rationale**:
- spec 016 明确软删走 `deleted_at`，软删行不会被列表查询命中，索引它们浪费空间。
- 部分索引体积小，更新成本低（删除操作不触发索引维护）。
- `(user_id, status, frequency, created_at)` 列顺序匹配既有 `ORDER BY user_id, status, frequency, created_at` 查询，且 `user_id` 等值过滤在最左。

**Alternatives considered**:
- 全索引 `(user_id, status, frequency, created_at)` — 索引软删行，浪费空间。
- 单列索引 `user_id` — 排序走 seq scan，不满足 SC-003。
- `status` 部分索引 — 无法支持 `ORDER BY frequency, created_at`。

### RQ-004: 路由懒加载对 E2E 有影响吗?

**Decision**: 无影响，但 E2E 需等待 Suspense fallback 消失。

**Rationale**:
- Playwright 默认 `autoWait` 会等待网络请求完成 + DOM 稳定，Suspense fallback 消失后即继续。
- 既有 E2E 用 `page.getByText(...)` / `page.getByRole(...)` 等待具体元素，fallback 不影响断言。
- 仅 `/login` 不懒加载（首屏），其他 16 个页面懒加载。

**Alternatives considered**:
- 全部 eager — 不解决 SC-004 首屏体积问题。
- 按路由组分 chunk（如 `resume-chunk` / `interview-chunk`）— 复杂度高，Vite 默认按 import 动态分割已够用。

### RQ-005: Vite manualChunks 用函数还是对象形式?

**Decision**: 函数形式 `(id) => { if (id.includes('node_modules/react')) return 'vendor'; ... }`。

**Rationale**:
- spec FR-051 明确要求函数形式。
- 对象形式 `{ react: ['react', 'react-dom'] }` 在动态 import 时有已知 bug（某些 chunk 会被重复打包）。
- 函数形式按 `id` 路径匹配，更灵活，支持 `@tanstack/react-query` 等 scoped package。

**Alternatives considered**:
- 对象形式 — 已知 bug，不选。
- 不配置 manualChunks — Vite 默认按 vendor 分割但策略不明确，vendor chunk hash 不稳定。

### RQ-006: metrics 端点如何避免高频抓取影响性能?

**Decision**: `prometheus_client` 默认 CollectorRegistry + `make_asgi_app()` 挂载到 FastAPI。

**Rationale**:
- `prometheus_client` 是 Python Prometheus 生态标准库，Collector 在内存中维护，scrape 时仅序列化。
- Gauge / Counter 的 `inc()` / `set()` 是 O(1) 原子操作，对业务请求零开销。
- `make_asgi_app()` 挂载到 `/metrics` 路径，FastAPI middleware 链外，不影响业务请求延迟。

**Alternatives considered**:
- 自实现 metrics endpoint — 重复造轮子。
- 用 Starlette `prometheus-fastapi-instrumentator` — 引入新依赖，且既有 5 类指标是自实现的，统一成本高。
- 定期 push 到 pushgateway — 拉模式（scrape）是 Prometheus 标准。

## Decisions Summary

| ID | Decision | Alternatives Rejected |
|----|----------|----------------------|
| D1 | `contextvars.ContextVar` + structlog `bind_contextvars` | OTel, threading.local, 手动 bind |
| D2 | `selectinload` + 内存聚合 | 窗口函数, subqueryload, batch COUNT |
| D3 | 部分索引 `WHERE deleted_at IS NULL` | 全索引, 单列索引 |
| D4 | `React.lazy` + Suspense，仅 `/login` eager | 全部 eager, 按路由组分 chunk |
| D5 | Vite `manualChunks` 函数形式 | 对象形式, 不配置 |
| D6 | `prometheus_client` + `make_asgi_app()` | 自实现, prometheus-fastapi-instrumentator, pushgateway |
