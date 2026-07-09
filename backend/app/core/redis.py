"""Redis async client (singleton) + pub/sub helpers + ARQ enqueue helper."""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as redis
from arq.connections import RedisSettings, create_pool

from app.core.config import get_settings
from app.observability.tracing import TraceContext, get_trace_context, inject_trace_context

_client: redis.Redis | None = None
_arq_pool: Any = None
_arq_pool_lock = asyncio.Lock()


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
                _arq_pool = await create_pool(
                    RedisSettings.from_dsn(settings.redis_url)
                )
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
    "close_redis",
    "build_arq_trace_metadata",
    "enqueue_job",
    "get_arq_pool",
    "get_redis",
    "publish",
    "redis_ping",
    "subscribe",
]
