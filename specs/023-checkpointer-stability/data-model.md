# Data Model: LangGraph Checkpointer 连接稳定性修复

**Date**: 2026-06-22

## No Schema Changes

本 feature 不改任何数据库表结构:
- `checkpoints` / `checkpoint_writes` / `checkpoint_blobs`（LangGraph checkpointer 表）保持既有 schema。
- `error_questions` / `resume_branches` / `users` 等业务表不变。
- 无新增 Alembic 迁移。

## Connection Pool Configuration (in-memory)

`AsyncPostgresSaver` 底层的 `AsyncConnectionPool` 配置:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `min_size` | 1 | 启动时预创建的连接数 |
| `max_size` | 10 | 连接池上限 |
| `max_idle` | 300s | 连接最大空闲时间（秒）|
| `reconnect_timeout` | 300s | 连接池整体重建超时 |
| `timeout` | 30s | 单次获取连接超时 |

## TCP Keepalive Configuration

psycopg connection `kwargs`:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `keepalives` | 1 | 启用 TCP keepalive |
| `keepalives_idle` | 30 | 空闲 30s 后开始探测 |
| `keepalives_interval` | 10 | 探测间隔 10s |
| `keepalives_count` | 5 | 5 次探测失败标记 dead |

## Metrics Entities (in-memory, prometheus_client)

| Metric | Type | Source | Description |
|--------|------|--------|-------------|
| `checkpointer_reconnect_total` | Counter | 本 feature 触发递增 | checkpointer 重连次数（022 定义埋点）|

埋点位置: `backend/app/agents/checkpointer.py` 的 `with_checkpointer_retry` 重建分支。

## Logging Events

| Event | Level | Fields | When |
|-------|-------|--------|------|
| `checkpointer.preheat ok` | info | `pool_config` | lifespan 预热成功 |
| `checkpointer.preheat_failed` | warning | `error` | lifespan 预热失败（DB 未就绪）|
| `checkpointer.reconnect` | info | `reason`, `thread_id?` | retry wrapper 触发重建 |
| `checkpointer.reconnect_failed` | error | `error`, `thread_id?` | 重建失败，抛 `CheckpointerUnavailableError` |

## Exceptions

新增 `backend/app/agents/exceptions.py`:

```python
class CheckpointerUnavailableError(Exception):
    """Checkpointer 重连失败，API 层应返回 503。"""
    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message)
        self.retry_after = retry_after
```

API 层 `agents.py` 路由捕获:
- `CheckpointerUnavailableError` → 503 + `{"detail": "面试服务暂时不可用，请稍后重试", "retry_after": 30}`

## No Other Entity Changes

- 5 个 graph 的 state schema 不变（业务逻辑零改动）。
- `ai_messages` 表不变。
- WebSocket / ARQ 队列不变。
