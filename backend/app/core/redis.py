"""Redis async client (singleton) + pub/sub helpers + ARQ enqueue helper."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, Literal

import redis.asyncio as redis
from arq.connections import RedisSettings, create_pool

from app.core.config import get_settings
from app.observability.tracing import TraceContext, get_trace_context, inject_trace_context

_client: redis.Redis | None = None
_arq_pool: Any = None
_arq_pool_lock = asyncio.Lock()

# ARQ 0.26.3 writes this health record with a TTL of interval + one second.
# API readiness and WorkerSettings intentionally share these constants.
ARQ_QUEUE_NAME = "arq:queue"
ARQ_HEALTH_CHECK_KEY = f"{ARQ_QUEUE_NAME}:health-check"
ARQ_HEALTH_CHECK_INTERVAL_SECONDS = 5.0
ARQ_HEALTH_CHECK_TTL_MS = int((ARQ_HEALTH_CHECK_INTERVAL_SECONDS + 1) * 1_000)
ARQ_HEALTH_STALE_AFTER_MS = int(ARQ_HEALTH_CHECK_INTERVAL_SECONDS * 1_000 + 500)
_ARQ_HEALTH_TTL_TOLERANCE_MS = 1_000
_ARQ_HEALTH_PATTERN = re.compile(
    r"^[A-Z][a-z]{2}-\d{2} \d{2}:\d{2}:\d{2} "
    r"j_complete=\d+ j_failed=\d+ j_retried=\d+ "
    r"j_ongoing=\d+ queued=\d+$"
)


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    """Fail-closed interpretation of the ARQ worker heartbeat."""

    state: Literal["up", "down", "stale"]
    reason: str
    age_ms: int | None = None


def classify_arq_worker_health(
    payload: str | bytes | None,
    pttl_ms: int,
) -> WorkerHealth:
    """Classify ARQ's health value using both its shape and remaining TTL."""
    if payload is None or pttl_ms == -2:
        return WorkerHealth("down", "missing")
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return WorkerHealth("down", "malformed")
    if not _ARQ_HEALTH_PATTERN.fullmatch(payload):
        return WorkerHealth("down", "malformed")
    if pttl_ms == -1:
        return WorkerHealth("stale", "no_ttl")
    if pttl_ms <= 0:
        return WorkerHealth("stale", "expired_heartbeat")
    if pttl_ms > ARQ_HEALTH_CHECK_TTL_MS + _ARQ_HEALTH_TTL_TOLERANCE_MS:
        return WorkerHealth("stale", "unexpected_ttl")

    age_ms = max(0, ARQ_HEALTH_CHECK_TTL_MS - pttl_ms)
    if age_ms > ARQ_HEALTH_STALE_AFTER_MS:
        return WorkerHealth("stale", "expired_heartbeat", age_ms)
    return WorkerHealth("up", "fresh", age_ms)


async def arq_worker_health() -> WorkerHealth:
    """Read the worker heartbeat value and TTL in one Redis round trip."""
    try:
        pipeline = get_redis().pipeline(transaction=False)
        pipeline.get(ARQ_HEALTH_CHECK_KEY)
        pipeline.pttl(ARQ_HEALTH_CHECK_KEY)
        payload, pttl_ms = await pipeline.execute()
        return classify_arq_worker_health(payload, int(pttl_ms))
    except Exception:
        return WorkerHealth("down", "transport_error")


def get_redis() -> redis.Redis:
    """Return the process-wide Redis client (lazy, connection-pooled)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
        )
    return _client


async def get_arq_pool():
    """Return the process-wide ARQ Redis pool (lazy, connection-pooled).

    Plain `redis.asyncio.Redis` does NOT have `enqueue_job`; only the
    `arq.connections.ArqRedis` returned by `create_pool` does. Without this
    helper every `enqueue_job(...)` call was silently raising AttributeError
    and being swallowed by try/except at the call sites — see the bug fix
    history: pdf_export / ability_diagnose never reached the worker.
    """
    global _arq_pool
    if _arq_pool is None:
        settings = get_settings()
        async with _arq_pool_lock:
            if _arq_pool is None:
                _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _arq_pool


def build_arq_trace_metadata(ctx: TraceContext | None = None) -> dict[str, str]:
    ctx = ctx or get_trace_context()
    headers = inject_trace_context(ctx)
    return {
        "run_id": headers.get("x-run-id", ""),
        "trace_id": headers["x-trace-id"],
        "span_id": headers["traceparent"].split("-")[2],
        "traceparent": headers["traceparent"],
    }


async def enqueue_job(name: str, **kwargs: Any) -> Any:
    """Enqueue an ARQ job by registered function name + kwargs.

    The kwargs become the ARQ function's parameters at execution time.
    """
    pool = await get_arq_pool()
    kwargs.setdefault("trace_ctx", build_arq_trace_metadata())
    return await pool.enqueue_job(name, **kwargs)


async def close_redis() -> None:
    global _client, _arq_pool
    if _client is not None:
        with contextlib.suppress(Exception):
            await _client.aclose()
        _client = None
    if _arq_pool is not None:
        with contextlib.suppress(Exception):
            await _arq_pool.aclose()
        _arq_pool = None


async def redis_ping() -> bool:
    """Health probe — returns True if PONG, False otherwise.

    Resilient to RuntimeError from a Redis client bound to a closed event loop
    (test fixtures rotate loops between modules) — drops the cached client and
    retries once on a fresh client.
    """
    try:
        return bool(await get_redis().ping())
    except RuntimeError:
        await close_redis()
        try:
            return bool(await get_redis().ping())
        except Exception:
            return False
    except Exception:
        return False


async def publish(channel: str, message: dict[str, Any]) -> int:
    """Publish a JSON message to a Redis channel.

    Returns the number of subscribers that received the message.
    """
    r = get_redis()
    payload = json.dumps(message, ensure_ascii=False)
    return await r.publish(channel, payload)


async def subscribe(channel: str) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator that yields JSON-decoded messages from a Redis channel.

    Usage:
        async for message in subscribe("lock:*"):
            await handle(message)
    """
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            data = raw["data"]
            if isinstance(data, str):
                yield json.loads(data)
            elif isinstance(data, (bytes, bytearray)):
                yield json.loads(data.decode("utf-8"))
            else:
                yield data
    finally:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await pubsub.unsubscribe(channel)
            await pubsub.close()


__all__ = [
    "ARQ_HEALTH_CHECK_INTERVAL_SECONDS",
    "ARQ_HEALTH_CHECK_KEY",
    "ARQ_HEALTH_CHECK_TTL_MS",
    "ARQ_QUEUE_NAME",
    "WorkerHealth",
    "arq_worker_health",
    "build_arq_trace_metadata",
    "classify_arq_worker_health",
    "close_redis",
    "enqueue_job",
    "get_arq_pool",
    "get_redis",
    "publish",
    "redis_ping",
    "subscribe",
]
