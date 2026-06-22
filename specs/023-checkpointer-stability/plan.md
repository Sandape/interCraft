# Implementation Plan: LangGraph Checkpointer 连接稳定性修复

**Branch**: `023-checkpointer-stability` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-checkpointer-stability/spec.md`

## Summary

补齐 v1 在 LangGraph checkpointer 连接管理方面的三项根因修复：(1) 连接池配置缺失（`min_size` / `max_size` / `max_idle` / `keepalive`）；(2) lifespan 不预热 checkpointer 表 schema；(3) retry 逻辑仅覆盖 interview 且 `submit_answer` 漏接。修复后 5 个 graph 的所有 checkpoint 操作统一走共享 `with_checkpointer_retry` wrapper（`asyncio.Lock` 保证并发安全重建），`backend/app/agents/checkpointer.py` 集中管理 `AsyncPostgresSaver` + `AsyncConnectionPool` 配置，lifespan startup 预热 + 失败降级为懒加载。零业务逻辑改动，零 API 契约改动，不升级 langgraph 主版本。

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI 0.110+, langgraph 0.2.x (保持 0.2.28), langgraph-checkpoint-postgres 1.0.x (保持 1.0.9), psycopg-pool 3.2+, psycopg 3.x, prometheus_client, structlog

**Storage**: PostgreSQL 15+ (checkpoints / checkpoint_writes / checkpoint_blobs 表，LangGraph checkpointer 自管理)

**Testing**: pytest (unit + integration with real PostgreSQL), Playwright (E2E round-1 + round-2)

**Target Platform**: Linux server (uvicorn + gunicorn)

**Project Type**: Web service with long-lived LangGraph agents

**Performance Goals**: idle 60s 后 submit_answer 100% 返回 200；服务重启首请求 ≤ 500ms；并发 10 请求触发重连仅重建 1 次

**Constraints**: 不改 API 契约；不改 graph 业务节点逻辑；不切换 sync checkpointer；不升级 langgraph 主版本；既有 E2E 零回归

**Scale/Scope**: 5 个 graph（interview / error_coach / resume_optimize / ability_diagnose / general_coach）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | `backend/app/agents/checkpointer.py` 作为共享库，封装 `get_checkpointer()` + `with_checkpointer_retry` + lifespan 预热；5 个 graph 不再各自实现 retry |
| II. CLI Interface | ✅ Pass | 本 feature 是连接管理内部优化，不新增 CLI；既有 CLI 不受影响 |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | 先写测试：unit 测 retry wrapper 对 `OperationalError` 的匹配 + 幂等性 + Lock；integration 测真实 idle 60s 后 submit_answer 200；lifespan 预热失败降级测试 |
| IV. Integration & Synchronization Testing | ✅ Pass | 集成测试命中真实 PostgreSQL，模拟 idle 断连（手动关闭底层连接）+ 并发触发重连；不允许「全 mock 快乐路径」 |
| V. Observability | ✅ Pass | `checkpointer_reconnect_total` Prometheus 指标（022 定义埋点位置，023 触发递增）；结构化日志 `checkpointer.preheat ok` / `checkpointer.preheat_failed` / `checkpointer.reconnect` 事件 |

**Gate Result**: PASS — 无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/023-checkpointer-stability/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (主要是 metrics, 无 schema 变更)
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── checkpointer-retry.md  # 共享 retry wrapper 契约
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/
│   │   ├── checkpointer.py        # 新增/重写: get_checkpointer + with_checkpointer_retry + lifespan 预热
│   │   ├── graphs/
│   │   │   ├── interview.py      # 修改: submit_answer 调用共享 wrapper (修复 graph.py:169 漏接)
│   │   │   ├── error_coach.py    # 修改: submit_answer / abort 调用共享 wrapper, 移除本地 retry
│   │   │   ├── resume_optimize.py # 修改: confirm / abort 调用共享 wrapper
│   │   │   ├── ability_diagnose.py # 修改: aget_state / ainvoke 调用共享 wrapper
│   │   │   └── general_coach.py   # 修改: send_message / close 调用共享 wrapper
│   │   └── exceptions.py         # 新增: CheckpointerUnavailableError
│   ├── api/
│   │   └── routes/
│   │       └── agents.py         # 修改: 捕获 CheckpointerUnavailableError → 503
│   └── main.py                    # 修改: lifespan 调用 checkpointer.preheat()
└── tests/
    ├── unit/
    │   ├── test_checkpointer_retry.py  # 新增: OperationalError 匹配 / 幂等 / Lock
    │   └── test_checkpointer_preheat.py # 新增: lifespan 预热成功/失败降级
    └── integration/
        ├── test_interview_idle_reconnect.py  # 新增: idle 60s 后 submit_answer 200
        ├── test_error_coach_idle_reconnect.py
        ├── test_concurrent_reconnect.py      # 新增: 10 并发请求仅重建 1 次
        └── test_arq_worker_retry.py          # 新增: ARQ worker 中 retry 生效
```

**Structure Decision**: 共享 `checkpointer.py` 作为单一 source of truth，5 个 graph 仅调用 wrapper 不持有 retry 逻辑。

## Implementation Strategy

### Phase A — 共享 retry wrapper + exceptions (US1 + US2 核心)

**目标**: 建立共享 retry 基础设施，先让 interview + error_coach 两个 P1 graph 接入。

1. TDD: 先写 `test_checkpointer_retry.py` 断言:
   - `OperationalError("connection is closed")` 触发重试。
   - `OperationalError("server closed the connection unexpectedly")` 触发重试。
   - 非匹配异常（如 `ProgrammingError`）不重试，直接抛出。
   - `aget_state` 幂等直接重试，`aupdate_state` 重试前先 `aget_state` 检查。
   - `asyncio.Lock` 保证并发仅重建 1 次。
2. 实现 `checkpointer.py`:
   - `get_checkpointer()`: 返回单例 `AsyncPostgresSaver`，配置显式连接池参数（FR-023/024）。
   - `with_checkpointer_retry`: async context manager，捕获 `OperationalError`，重建 checkpointer（持锁），重试一次。
   - `CheckpointerUnavailableError`: 重连失败时抛出。
3. 新增 `exceptions.py`: `CheckpointerUnavailableError`。
4. 修改 `api/routes/agents.py`: 捕获 `CheckpointerUnavailableError` → 503 + `retry_after` 提示。
5. 修改 `interview/graph.py:169` 的 `submit_answer`: 改用 `with_checkpointer_retry`（修复漏接 bug）。
6. 修改 `error_coach/graph.py` 的 `submit_answer` / `abort`: 改用 wrapper。

### Phase B — 扩展到其余 3 graph (US3 + US4 + US5)

**目标**: resume_optimize + ability_diagnose + general_coach 接入 wrapper。

1. TDD: 先写 `test_resume_optimize_idle_reconnect.py` / `test_general_coach_idle_reconnect.py`。
2. 修改 `resume_optimize/graph.py` 的 `confirm` / `abort`。
3. 修改 `ability_diagnose/graph.py` 的 `aget_state` / `ainvoke`（ARQ worker 上下文）。
4. 修改 `general_coach/graph.py` 的 `send_message` / `close`。
5. TDD: 先写 `test_arq_worker_retry.py` 断言 ARQ worker 中 retry 生效。
6. 移除 5 个 graph 的既有 `_is_checkpointer_alive` / `_rebuild_checkpointer` 本地实现（FR-013），统一调用 wrapper。

### Phase C — lifespan 预热 + 连接池配置 (US6)

**目标**: 服务启动时预热 checkpointer 表 schema，首请求无延迟。

1. TDD: 先写 `test_checkpointer_preheat.py` 断言:
   - lifespan 启动后 `pg_tables` 含 `checkpoint%` 表。
   - 预热失败（DB 未就绪）服务仍启动，日志含 `checkpointer.preheat_failed` warning。
   - 预热成功日志含 `checkpointer.preheat ok` + 连接池参数。
2. 修改 `main.py` lifespan: 调用 `checkpointer.preheat()` = `get_checkpointer()` + `setup()` + `pool.open()`。
3. 实现 `checkpointer.preheat()` 函数，try/except 不阻塞启动。
4. 配置 `AsyncPostgresSaver` 连接池（FR-023）: `min_size=1, max_size=10, max_idle=300, reconnect_timeout=300, timeout=30`。
5. 配置 TCP keepalive（FR-024）: `keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5`。
6. 启用 `check_connection` 回调（FR-025）: psycopg-pool 3.2+ 的 `check` 参数，`SELECT 1` 健康检查。

### Phase D — 跨切面验证 + 回归

**目标**: 既有 E2E 零回归 + SC 全部达成。

1. 集成测试: idle 60s → submit_answer 200（5 个 graph 各一个测试）。
2. 并发测试: 10 个并发请求触发重连，日志计数仅 1 次「重建」事件。
3. 跑 round-1 + round-2 E2E（21/21）+ 后端 88+ 单测。
4. 验证 SC-001~007: 5 agent idle 100% 200、重启首请求 ≤ 500ms、`checkpointer_reconnect_total` 可观测、代码净减少、E2E 零回归、连接池配置可见、并发重连仅 1 次。

## Complexity Tracking

> 无 Constitution Check 违规，本节为空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
