"""[REQ-048 US2 T054] Redis cache wrapper for drill candidate selection.

Implements the cache key + TTL contract from FR-015 + AC-09b + AC-09c.

Cache key formula (locked in data-model.md §2.2):

    drill_cache:{user_id}:{key_hex}
    key_hex = sha256(jd_text.encode('utf-8') + error_pool_hash.encode('utf-8'))[:32]

The user_id is opaque (any string UUID). The ``error_pool_hash`` is a
caller-supplied SHA256 hex string that represents the user's current
error question pool (typically ``sha256(sorted(source_question_id list))``).

Value stored as a JSON list of ``source_question_id`` (strings) plus a
``cache_key`` envelope field for audit.

The TTL is configurable (default 300s = 5 min per FR-015 / SC-013).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


CACHE_KEY_PREFIX = "drill_cache"
DEFAULT_TTL_SECONDS = 300
KEY_HEX_LENGTH = 32


def build_cache_key(
    user_id: str,
    jd_text: str,
    error_pool_hash: str,
) -> str:
    """Compute the canonical cache key for (user, JD, error-pool) tuple.

    Formula (locked at AC-09c / data-model.md §2.2):

        key_hex = sha256(jd_text + error_pool_hash).hexdigest()[:32]
        full_key = drill_cache:{user_id}:{key_hex}

    Total key length: len("drill_cache:") + 36 (uuid) + 1 (":") + 32 (hex) = 70.
    """
    digest = hashlib.sha256(
        jd_text.encode("utf-8") + error_pool_hash.encode("utf-8")
    ).hexdigest()[:KEY_HEX_LENGTH]
    return f"{CACHE_KEY_PREFIX}:{user_id}:{digest}"


def compute_error_pool_hash(source_question_ids: list[str]) -> str:
    """Compute a stable hash for the user's error pool.

    Sort the input IDs to make the hash order-independent, then SHA256 hex.
    """
    canonical = ",".join(sorted(str(x) for x in source_question_ids if x))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class DrillCacheEntry:
    user_id: str
    cache_key: str
    source_question_ids: list[str]
    cached_at_iso: str
    ttl_seconds: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "cache_key": self.cache_key,
                "source_question_ids": list(self.source_question_ids),
                "cached_at": self.cached_at_iso,
                "ttl_seconds": int(self.ttl_seconds),
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str | bytes, *, user_id: str, ttl_seconds: int) -> "DrillCacheEntry":
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return cls(
            user_id=user_id,
            cache_key=str(data.get("cache_key", "")),
            source_question_ids=list(data.get("source_question_ids", [])),
            cached_at_iso=str(data.get("cached_at", "")),
            ttl_seconds=int(data.get("ttl_seconds", ttl_seconds)),
        )


async def get_cached(
    redis_client: redis.Redis,
    user_id: str,
    jd_text: str,
    error_pool_hash: str,
) -> DrillCacheEntry | None:
    """Read a cached entry; returns ``None`` on miss."""
    key = build_cache_key(user_id, jd_text, error_pool_hash)
    try:
        raw = await redis_client.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("drill.cache.get_failed", key=key, exc=str(exc))
        return None
    if raw is None:
        return None
    try:
        return DrillCacheEntry.from_json(raw, user_id=user_id, ttl_seconds=DEFAULT_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("drill.cache.parse_failed", key=key, exc=str(exc))
        return None


async def set_cached(
    redis_client: redis.Redis,
    entry: DrillCacheEntry,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """Write a cached entry with TTL; returns True on success."""
    try:
        await redis_client.set(entry.cache_key, entry.to_json(), ex=ttl_seconds)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "drill.cache.set_failed",
            key=entry.cache_key,
            exc=str(exc),
        )
        return False


async def invalidate(
    redis_client: redis.Redis,
    user_id: str,
    jd_text: str,
    error_pool_hash: str,
) -> bool:
    """Delete a cached entry; returns True if a key was removed."""
    key = build_cache_key(user_id, jd_text, error_pool_hash)
    try:
        removed = await redis_client.delete(key)
        return bool(removed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("drill.cache.delete_failed", key=key, exc=str(exc))
        return False


__all__ = [
    "CACHE_KEY_PREFIX",
    "DEFAULT_TTL_SECONDS",
    "KEY_HEX_LENGTH",
    "DrillCacheEntry",
    "build_cache_key",
    "compute_error_pool_hash",
    "get_cached",
    "invalidate",
    "set_cached",
]