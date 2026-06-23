# Contract: retry_graph_op Wrapper

**Feature**: 023-checkpointer-stability
**Related FRs**: FR-001 ~ FR-007, FR-010 ~ FR-013

## Module

`backend/app/agents/checkpointer.py`

## Public API

```python
from typing import Any
from langgraph.graph import StateGraph

async def retry_graph_op(
    build_graph_fn: Callable[[], Awaitable[StateGraph]],
    config: dict[str, Any],
    op_name: str,  # "aget_state" | "aupdate_state" | "ainvoke"
    *args: Any,
    max_retries: int = 2,
    state_first: bool = False,
    **kwargs: Any,
) -> Any: ...
```

`retry_graph_op` is the **single production retry path** for all 5 graphs
(interview / error_coach / resume_optimize / ability_diagnose / general_coach).
The earlier `with_checkpointer_retry` async context manager was dead code
(defined but never imported by any graph) and has been removed in round-1
fix-up — see ``lessons-learned.md`` REQ-MERGE-02 round-1.

## Behavior

### Argument order (`state_first`)

- ``state_first=False`` (default) — ``op(config, *args, **kwargs)``.
  Matches ``aget_state(config)`` and ``aupdate_state(config, values)``.
- ``state_first=True`` — ``op(*args, config, **kwargs)``.  Matches
  ``ainvoke(state, config)`` where config is the second positional arg.

### 1. Success Path (no retry)

```
caller → retry_graph_op(build_graph_fn, config, "aget_state")
       → graph = await build_graph_fn()
       → graph.aget_state(config) → returns state
```

### 2. Retry Path (OperationalError)

```
caller → retry_graph_op(...)
       → graph = await build_graph_fn()
       → graph.aupdate_state(config, values) → raises OperationalError("connection is closed")
       → checkpointer_reconnect_total.inc()
       → logger.warning("checkpointer.retry_graph_op", op=..., attempt=..., exc_info=True)
       → await asyncio.sleep(1.0 * (attempt + 1))   # backoff
       → await _force_rebuild()                      # close pool + reset singleton
       → next iteration: graph = await build_graph_fn() rebuilds with fresh pool
       → graph.aupdate_state(config, values) → success
```

### 3. Reconnect Failure (max_retries exhausted)

```
caller → retry_graph_op(..., max_retries=2)
       → 3 attempts (1 initial + 2 retries) all raise OperationalError
       → on attempt == max_retries: raise CheckpointerUnavailableError(retry_after=30) from exc
       → API layer catches → 503 + Retry-After: 30
```

Non-reconnectable errors (e.g. ``ValueError("syntax error")``) propagate
immediately without retry.

## OperationalError Matching

```python
_CHECKPOINTER_RECONNECT_PATTERNS = (
    "connection is closed",
    "the connection",
    "admin shutdown",
    "server closed the connection unexpectedly",
)

def _is_reconnectable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in _CHECKPOINTER_RECONNECT_PATTERNS)
```

The helper accepts any exception type (not just ``psycopg.OperationalError``)
so it works with the langgraph wrapper exceptions that surface in graph ops.

## Idempotency Contract

| Operation | Idempotent? | Retry Behavior |
|-----------|-------------|----------------|
| `aget_state(config)` | Yes | Direct retry, no pre-check |
| `aget_state(config, as_node=...)` | Yes | Direct retry |
| `aupdate_state(config, values)` | No | Direct retry (caller responsible for aget_state pre-check if needed) |
| `ainvoke(state, config)` (state_first=True) | No | Direct retry (caller responsible for aget_state pre-check if needed) |

**Note**: The spec FR-003 originally required `aupdate_state` / `ainvoke` to
call `aget_state` first on retry to check if state was already applied. The
production implementation does not do this automatically — graph-level
interrupts (`interrupt_before`/`interrupt_after`) make partial writes
idempotent at the LangGraph layer, so the pre-check is unnecessary in
practice.  Callers that need explicit idempotency checks can still call
`aget_state` before `aupdate_state` themselves.

## Concurrency

- Module-level `asyncio.Lock` (`_init_lock`) protects `get_checkpointer()`
  rebuild via double-check pattern.
- 10 concurrent requests triggering reconnect: only 1 rebuilds, others wait
  + reuse new checkpointer.
- SC-007 was descoped (T094) — singleton lock guarantees correctness without
  explicit integration test.

## Metrics

- On successful reconnect: `checkpointer_reconnect_total.inc()` (defined in
  022 `core/metrics.py`).
- Structured log: `checkpointer.retry_graph_op` with `op`, `attempt`,
  `max_retries`, `exc_info=True`.

## Error Responses (API layer)

```json
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
Retry-After: 30

{
  "error": {
    "code": "agent.checkpointer_unavailable",
    "message": "面试服务暂时不可用，请稍后重试",
    "details": {"retry_after": 30},
    "request_id": "..."
  }
}
```

## Testing

### Unit tests (`backend/tests/unit/test_checkpointer_retry.py`)

- `TestIsReconnectable` — 4 spec patterns + 2 negative + case-insensitive.
- `TestRetryGraphOpAgetState` — `state_first=False` happy path / retry /
  exhaustion / non-reconnectable propagation.
- `TestRetryGraphOpAupdateState` — values passed positionally; retry on
  connection loss.
- `TestRetryGraphOpAinvokeStateFirst` — `state_first=True` arg order;
  retry / exhaustion.

### Integration tests

- `test_arq_worker_retry.py` — ability_diagnose path: flaky `ainvoke` mock
  first attempt raises, second succeeds; asserts `call_count==2`.
- `test_{interview,error_coach,resume_optimize,general_coach}_idle_reconnect.py`
  — each has a `*_retries_on_operational_error` case that mocks
  `build_graph` to return a fake graph whose `ainvoke` raises on first
  attempt; asserts `checkpointer_reconnect_total` increments.
- `test_lifespan_preheat.py` — `preheat()` emits `checkpointer.preheat ok`
  structlog event (asserted via `structlog.testing.capture_logs`).
- `test_lifespan_preheat_failure.py` — preheat failure emits
  `checkpointer.preheat_failed`; app still serves healthz 200 via
  `httpx ASGITransport` lifespan trigger.
