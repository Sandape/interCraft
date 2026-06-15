"""Redis async client (singleton) + pub/sub helpers."""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


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


async def close_redis() -> None:
    global _client
    if _client is not None:
        with contextlib.suppress(Exception):
            await _client.aclose()
        _client = None


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


__all__ = ["close_redis", "get_redis", "publish", "redis_ping", "subscribe"]
