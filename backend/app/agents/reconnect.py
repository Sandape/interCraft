"""REQ-043 US-2 FR-006 — 3-tier reconnect strategy.

Spec contract (FR-006 + SC-005):
- L1: 3 fast retries with 1s sleep between attempts.
- L2: 1 connection rebuild with 2s sleep (per pool, scoped).
- L3: write ``state.error`` + Sentry alert; raise
  ``CheckpointerUnavailableError(retry_after=30)`` so the API
  layer returns 503 and the frontend prompts "retry later".

Design (per L041-005):
- ``CheckpointerUnavailableError`` subclasses ``RuntimeError`` so the
  041 US1 ``except RuntimeError`` pattern (LLMInvokeError,
  MaxIterationsReached) catches it in the same handler.
- Per-pool scope: only the failing pool is rebuilt (never all 8).
- Per-op fail-open: non-reconnectable errors propagate immediately,
  bypassing L1/L2/L3.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from app.agents.checkpointer_pool import (
    POOL_CONFIGS,
    _create_pool,
    _pools,
    get_checkpointer_pool,
    get_pool_id,
)
from app.agents.exceptions import CheckpointerUnavailableError

logger = structlog.get_logger("agents.reconnect")

# Reconnectable exception patterns (mirror 023 _CHECKPOINTER_RECONNECT_PATTERNS).
_RECONNECTABLE_PATTERNS = (
    "connection is closed",
    "the connection",
    "admin shutdown",
    "server closed the connection unexpectedly",
)


def _is_reconnectable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(pattern in msg for pattern in _RECONNECTABLE_PATTERNS)


def _record_attempt(level: str, attempt: int, error: str, outcome: str) -> None:
    """Log a structured reconnect-attempt event.

    Schema matches spec Key Entities ``ReconnectAttempt``.
    """
    logger.info(
        "checkpointer.reconnect_attempt",
        level=level,
        attempt=attempt,
        error=error,
        outcome=outcome,
        attempted_at=datetime.now(tz=timezone.utc).isoformat(),
    )


async def three_tier_reconnect(
    user_id: str,
    op_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute ``pool.<op_name>(*args, **kwargs)`` with 3-tier reconnect.

    Args:
        user_id: Used to hash to a pool (8-pool sharding per FR-005).
        op_name: Attribute name on the saver (``aget_state``,
            ``aupdate_state``, etc.).
        *args / **kwargs: Forwarded to the underlying op.

    Returns:
        Whatever ``op_name`` returns on success.

    Raises:
        CheckpointerUnavailableError: After L1 + L2 exhaust retries
            (L3). ``retry_after=30`` so the API layer returns 503 with
            a Retry-After hint.
    """
    pool = await get_checkpointer_pool(user_id)
    pool_id = get_pool_id(user_id)

    # L1 — 3 fast retries with 1s sleep between attempts.
    last_exc: BaseException | None = None
    for attempt in range(1, 4):
        try:
            op = getattr(pool, op_name)
            return await op(*args, **kwargs)
        except Exception as exc:
            if not _is_reconnectable(exc):
                # Non-reconnectable error → propagate immediately.
                raise
            last_exc = exc
            _record_attempt(
                level="L1",
                attempt=attempt,
                error=str(exc),
                outcome="retry" if attempt < 3 else "fail",
            )
            if attempt < 3:
                await asyncio.sleep(1.0)

    # L2 — rebuild the pool (scoped to pool_id), then 1 more attempt.
    _record_attempt(level="L2", attempt=1, error=str(last_exc), outcome="rebuild")
    await asyncio.sleep(2.0)
    try:
        cfg = POOL_CONFIGS[pool_id]
        new_pool = await _create_pool(cfg)
        _pools[pool_id] = new_pool
        pool = new_pool
    except Exception as exc:
        _record_attempt(level="L2", attempt=1, error=str(exc), outcome="fail")
        last_exc = exc
    else:
        try:
            op = getattr(pool, op_name)
            return await op(*args, **kwargs)
        except Exception as exc:
            if not _is_reconnectable(exc):
                raise
            last_exc = exc
            _record_attempt(
                level="L2", attempt=2, error=str(exc), outcome="fail"
            )

    # L3 — Sentry alert + raise CheckpointerUnavailableError.
    _record_attempt(level="L3", attempt=1, error=str(last_exc), outcome="fail")
    _emit_sentry_alert(user_id=user_id, op_name=op_name, error=str(last_exc))
    raise CheckpointerUnavailableError(
        f"Graph operation {op_name} failed after L1+L2: {last_exc}",
        retry_after=30,
    ) from last_exc


def _emit_sentry_alert(user_id: str, op_name: str, error: str) -> None:
    """Send an alert to Sentry (best-effort, never raises).

    If ``sentry-sdk`` is not installed or the DSN is not configured,
    this is a no-op. Per spec AC-SC-005, the alert must reach Sentry
    in ≤ 30s — we use the synchronous transport for the lowest
    possible latency in the failure path.
    """
    try:
        import sentry_sdk  # type: ignore[import-not-found]

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("reconnect.level", "L3")
            scope.set_tag("checkpointer.op", op_name)
            scope.set_user({"id": user_id})
            sentry_sdk.capture_message(
                f"checkpointer L3 fail: {op_name} for {user_id}: {error}",
                level="error",
            )
    except Exception:
        # Sentry not installed or not configured — log and move on.
        logger.warning(
            "checkpointer.sentry_alert_unavailable",
            user_id=user_id,
            op_name=op_name,
            exc_info=True,
        )


__all__ = ["three_tier_reconnect"]