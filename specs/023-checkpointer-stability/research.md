# Research: LangGraph Checkpointer 连接稳定性修复

**Date**: 2026-06-22

## Research Questions

### RQ-001: psycopg.OperationalError 的匹配模式如何覆盖所有断连场景?

**Decision**: 匹配 `str(exc).lower()` 中含以下任一子串（大小写不敏感）:
- `"connection is closed"` — psycopg 连接被显式关闭
- `"the connection"` — 通用连接断开
- `"admin shutdown"` — PostgreSQL `pg_terminate_backend`
- `"server closed the connection unexpectedly"` — 服务端 idle 超时关闭

**Rationale**:
- psycopg 3.x 对不同断连场景抛 `OperationalError`，message 文本稳定。
- `asyncpg` 的 `ConnectionFailureError` 不适用（本项目用 psycopg）。
- 不匹配 `InterfaceError`（连接池已关闭），那是另一类错误需独立处理（可走 lifespan 重启）。
- `OperationalError` 也可能因 SQL 语法错误触发，但那种情况 message 不会含上述子串，不误匹配。

**Alternatives considered**:
- 匹配所有 `OperationalError` — 误重试 SQL 语法错误，浪费一次 retry。
- 匹配 PostgreSQL SQLSTATE (`08006`) — psycopg 3.x 异常含 `diag.sqlstate` 属性，但 LangGraph checkpointer 包装层可能丢失，不稳。
- 仅匹配 `"connection is closed"` — 不覆盖 `admin shutdown` 场景。

### RQ-002: 重试幂等性如何保证 (aupdate_state 可能部分写入)?

**Decision**: 分两类处理:
- **幂等操作** (`aget_state`): 直接重试，无副作用。
- **非幂等操作** (`aupdate_state` / `ainvoke`): 重试前先 `aget_state(thread_id)`，检查当前 state:
  - 若 state 已含本次更新的 channel → 跳过更新，返回当前 state。
  - 若 state 未更新 → 执行更新。
- 对 `aupdate_state(as_node=...)` 还需检查 `pending_writes`，避免重复写入。

**Rationale**:
- LangGraph 的 `aupdate_state` 本身不保证幂等，需调用方判断。
- `aget_state` 返回完整 `StateSnapshot`（含 `next` / `values` / `tasks`），可判断是否已到目标状态。
- `ainvoke` 是更高层 API，重试前检查 `aget_state` 的 `next` 节点是否为目标节点的后继。

**Alternatives considered**:
- 直接重试不检查 — 可能重复写入 state（如 frequency 递减两次）。
- 全部走 `aget_state` + 手动应用更新 — 复杂度高，等于重新实现 LangGraph。
- 引入分布式锁 — 过度设计，单进程 `asyncio.Lock` 已够。

### RQ-003: 并发触发重连时如何避免重复重建?

**Decision**: 模块级 `asyncio.Lock` 保护 `get_checkpointer()` 重建路径。

```python
_rebuild_lock = asyncio.Lock()
_checkpointer: AsyncPostgresSaver | None = None

async def get_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer
    if _checkpointer is not None and await _is_alive(_checkpointer):
        return _checkpointer
    async with _rebuild_lock:
        # double-check after acquiring lock
        if _checkpointer is not None and await _is_alive(_checkpointer):
            return _checkpointer
        _checkpointer = await _build_checkpointer()
        return _checkpointer
```

**Rationale**:
- `asyncio.Lock` 是单进程协程级锁，对单 worker 部署足够。
- 多 worker 部署（gunicorn 多进程）每个进程独立 lock，各自重建一次可接受。
- 不用 `threading.Lock`（asyncio 上下文会阻塞 event loop）。
- 不用 Redis 分布式锁 — 过度设计，每个 worker 各自重建 checkpointer 不影响正确性。

**Alternatives considered**:
- 不加锁 — N 个并发请求各自重建 N 次，浪费连接。
- 每请求独立 checkpointer — 连接池爆炸，违反 `max_size=10`。
- Redis 分布式锁 — 跨进程协调成本 > 收益。

### RQ-004: lifespan 预热失败如何降级?

**Decision**: try/except + warning 日志，不抛异常，服务继续启动。

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        checkpointer = await get_checkpointer()
        await checkpointer.setup()  # 创建表 schema
        await checkpointer.pool.open()  # 显式 open 连接池
        logger.info("checkpointer.preheat ok", pool_config={...})
    except Exception as e:
        logger.warning("checkpointer.preheat_failed", error=str(e))
        # 降级为懒加载: 首次 agent 调用时 get_checkpointer() 重建
    yield
```

**Rationale**:
- DB 未就绪时（如启动顺序问题）服务仍可启动，避免级联故障。
- 懒加载路径与预热路径共享 `get_checkpointer()`，逻辑一致。
- 预热失败 warning 日志便于运维感知，可接 alert。
- 不重试预热 — DB 长时间未就绪说明环境问题，重试无意义。

**Alternatives considered**:
- 预热失败直接抛异常 — 服务无法启动，影响其他功能（不依赖 checkpointer 的接口）。
- 预热失败无限重试 — 启动卡死。
- 预热失败降级后静默 — 运维无法感知，首请求才发现问题。

### RQ-005: 连接池参数如何选?

**Decision**: `min_size=1, max_size=10, max_idle=300, reconnect_timeout=300, timeout=30` + TCP keepalive `keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5`。

**Rationale**:
- `min_size=1`: 启动时仅 1 个常驻连接，不浪费资源。
- `max_size=10`: 5 个 agent + ARQ worker + WS 连接，10 个够用（每请求持连接时间 < 100ms）。
- `max_idle=300s`: 比常见 NAT idle timeout（60-120s）长，但短于 PostgreSQL `idle_in_transaction_session_timeout`（建议 300s+）。
- `reconnect_timeout=300s`: 连接池整体重建的超时，5 分钟足够 DB 恢复。
- `timeout=30s`: 单次获取连接的超时，避免请求堆积。
- TCP keepalive `idle=30s`: 每 30s 探测一次，早于 NAT timeout（通常 60s）发现死连接。
- `keepalives_count=5` × `interval=10s` = 50s 探测失败后标记 dead，总探测时间 30+50=80s < `max_idle=300s`。

**Alternatives considered**:
- `max_size=20` — 过大，PostgreSQL `max_connections` 默认 100，5 个 worker × 20 = 100 会打满。
- `max_idle=60s` — 太短，频繁重建连接。
- 不配置 keepalive — NAT 30s idle kill 仍会发生。
- 用 `pgbouncer` — 引入新依赖，v1 不做。

### RQ-006: ARQ worker 中 retry 如何生效（无 HTTP request_id）?

**Decision**: ARQ worker `on_job_start` 钩子中 `bind_contextvars(request_id=job_id)`，worker 中调用 agent graph 时 retry wrapper 行为与 HTTP 上下文一致。

**Rationale**:
- ARQ worker 是独立进程，但 Python `contextvars` 在同进程内有效。
- `job_id` 是 ARQ 任务唯一标识，可作为 request_id 用于日志关联。
- retry wrapper 本身不依赖 request_id，仅依赖 `get_checkpointer()` 单例。
- worker 中的 LLM 调用日志会带上 `request_id=job_id`，便于排障。

**Alternatives considered**:
- ARQ worker 独立 retry 实现 — 重复代码，违反 DRY。
- 不在 worker 中加 retry — ability_diagnose 任务失败率高，进 dead letter。
- 给 retry wrapper 传 `request_id` 参数 — 侵入性强，5 个 graph 都要改签名。

## Decisions Summary

| ID | Decision | Alternatives Rejected |
|----|----------|----------------------|
| D1 | `OperationalError` 子串匹配（4 个模式） | 匹配所有 OperationalError, SQLSTATE, 单一模式 |
| D2 | 幂等操作直接重试，非幂等先 `aget_state` 检查 | 直接重试不检查, 全部 aget_state, 分布式锁 |
| D3 | `asyncio.Lock` + double-check | 无锁, 每请求独立 checkpointer, Redis 锁 |
| D4 | lifespan 预热 try/except 降级懒加载 | 抛异常, 无限重试, 静默降级 |
| D5 | `min_size=1, max_size=10, max_idle=300, keepalive=30/10/5` | max_size=20, max_idle=60, 无 keepalive, pgbouncer |
| D6 | ARQ worker `on_job_start` 绑定 `request_id=job_id` | 独立 retry, 不加 retry, 传参 |
