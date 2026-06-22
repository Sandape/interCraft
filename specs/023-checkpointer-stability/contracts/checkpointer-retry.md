# Contract: with_checkpointer_retry Wrapper

**Feature**: 023-checkpointer-stability
**Related FRs**: FR-001 ~ FR-007, FR-010 ~ FR-013

## Module

`backend/app/agents/checkpointer.py`

## Public API

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, TypeVar

T = TypeVar("T")

@asynccontextmanager
async def with_checkpointer_retry(
    *,
    thread_id: str,
    operation: str,  # "aget_state" | "aupdate_state" | "ainvoke"
) -> AsyncIterator[AsyncPostgresSaver]:
    """Retry wrapper for LangGraph checkpointer operations.

    Yields a healthy AsyncPostgresSaver. On OperationalError (connection dropped),
    rebuilds the checkpointer once (under asyncio.Lock) and retries the operation.

    For non-idempotent operations (aupdate_state / ainvoke), callers MUST
    check state via aget_state before re-applying writes.

    Raises CheckpointerUnavailableError if reconnect fails.
    """
    ...
```

## Behavior

### 1. Success Path (no retry)

```
caller → with_checkpointer_retry → get_checkpointer() → yields checkpointer
caller does aget_state / aupdate_state → success → exits wrapper
```

### 2. Retry Path (OperationalError)

```
caller → with_checkpointer_retry → get_checkpointer() → yields checkpointer
caller does aupdate_state → raises OperationalError("connection is closed")
wrapper catches → acquires _rebuild_lock → rebuilds checkpointer
wrapper retries → get_checkpointer() → yields new checkpointer
caller does aget_state first (idempotency check) → aupdate_state → success
```

### 3. Reconnect Failure

```
caller → with_checkpointer_retry → get_checkpointer() → yields checkpointer
caller does aget_state → raises OperationalError
wrapper catches → acquires _rebuild_lock → rebuild fails (DB unreachable)
wrapper raises CheckpointerUnavailableError(retry_after=30)
API layer catches → returns 503
```

## OperationalError Matching

```python
_RECONNECT_PATTERNS = [
    "connection is closed",
    "the connection",
    "admin shutdown",
    "server closed the connection unexpectedly",
]

def _is_reconnectable(exc: Exception) -> bool:
    if not isinstance(exc, psycopg.OperationalError):
        return False
    msg = str(exc).lower()
    return any(p in msg for p in _RECONNECT_PATTERNS)
```

## Idempotency Contract

| Operation | Idempotent? | Retry Behavior |
|-----------|-------------|----------------|
| `aget_state(thread_id)` | Yes | Direct retry, no pre-check |
| `aget_state(thread_id, as_node=...)` | Yes | Direct retry |
| `aupdate_state(thread_id, values)` | No | Retry: `aget_state` first, check if values already applied |
| `ainvoke(thread_id, input)` | No | Retry: `aget_state` first, check if `next` is past target node |

## Concurrency

- Module-level `asyncio.Lock` (`_rebuild_lock`) protects `get_checkpointer()` rebuild.
- 10 concurrent requests triggering reconnect: only 1 rebuilds, others wait + reuse new checkpointer.
- Double-check pattern after acquiring lock (避免重复重建）。

## Metrics

- On successful reconnect: `checkpointer_reconnect_total.inc()` (022 定义埋点位置)。
- `checkpointer.reconnect` structured log: `{reason: "OperationalError", thread_id: "...", operation: "aupdate_state"}`.

## Error Responses (API layer)

```json
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
Retry-After: 30

{
  "detail": "面试服务暂时不可用，请稍后重试",
  "retry_after": 30
}
```

## Testing

- 单测 `test_checkpointer_retry.py`:
  - Mock `AsyncPostgresSaver.aget_state` 抛 `OperationalError("connection is closed")` → 断言 wrapper 重建 + 重试。
  - 非 `OperationalError`（如 `ProgrammingError`）→ 直接抛出，不重试。
  - `aupdate_state` 重试前先调用 `aget_state`（mock 验证调用顺序）。
  - 10 并发 `aget_state` 触发 reconnect → 断言 `get_checkpointer` 重建仅 1 次。
- 集成测试:
  - 手动 `pg_terminate_backend` 关闭连接 → 下次 wrapper 调用重建 + 重试成功。
  - 关闭 PostgreSQL → wrapper 抛 `CheckpointerUnavailableError` → API 返回 503。
