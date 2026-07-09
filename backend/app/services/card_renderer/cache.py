"""[REQ-048 T084] Card render cache.

Mirrors the US2 drill cache contract (see
``app/agents/interview/drill_helpers/cache.py``) but with a 7-day TTL
(FR-063 / AC-22 / AC-24) keyed on ``hash(JD + plan fields)``.

The cache is a thin wrapper around ``redis.asyncio.Redis`` that:

- writes the rendered JPG bytes (base64-enveloped so JSON safe) plus
  the file size + sha256 for hit verification;
- reads them back when ``X-Card-Cache-Hit: true`` should be set on the
  HTTP response;
- gracefully degrades to ``None`` on any Redis error (AC-22 — never
  fail the API because the cache layer is down).

Key formula (locked at AC-09c style):

    card_cache:{user_id}:{key_hex}
    key_hex = sha256(jd_text + plan_hash).hexdigest()[:32]

Plan hash is a SHA256 over the JSON-canonicalised plan dict so that any
field change (focus_areas, suggested_questions, etc.) invalidates the
entry.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass

import redis.asyncio as redis

from app.core.config import get_settings


logger = logging.getLogger(__name__)


CARD_CACHE_KEY_PREFIX = "card_cache"
CARD_CACHE_KEY_HEX_LENGTH = 32
CARD_CACHE_DEFAULT_TTL_DAYS = 7


def compute_plan_hash(plan: dict) -> str:
    """SHA256 over JSON-canonicalised plan dict.

    Sort keys + ensure_ascii=False so the hash is stable across Python
    sessions / locales.
    """
    canonical = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_card_cache_key(user_id: str, jd_text: str, plan_hash: str) -> str:
    """Compute the canonical card cache key.

    Formula mirrors the drill cache (AC-09c):

        key_hex = sha256(jd_text + plan_hash).hexdigest()[:32]
        full_key = card_cache:{user_id}:{key_hex}
    """
    digest = hashlib.sha256(
        jd_text.encode("utf-8") + plan_hash.encode("utf-8")
    ).hexdigest()[:CARD_CACHE_KEY_HEX_LENGTH]
    return f"{CARD_CACHE_KEY_PREFIX}:{user_id}:{digest}"


@dataclass
class CardCacheEntry:
    user_id: str
    cache_key: str
    image_bytes_b64: str
    sha256_hex: str
    bytes_total: int
    size_variant: str
    cached_at_iso: str
    ttl_seconds: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "cache_key": self.cache_key,
                "image_bytes_b64": self.image_bytes_b64,
                "sha256_hex": self.sha256_hex,
                "bytes_total": int(self.bytes_total),
                "size_variant": self.size_variant,
                "cached_at": self.cached_at_iso,
                "ttl_seconds": int(self.ttl_seconds),
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str | bytes, *, user_id: str, ttl_seconds: int) -> "CardCacheEntry":
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return cls(
            user_id=user_id,
            cache_key=str(data.get("cache_key", "")),
            image_bytes_b64=str(data.get("image_bytes_b64", "")),
            sha256_hex=str(data.get("sha256_hex", "")),
            bytes_total=int(data.get("bytes_total", 0)),
            size_variant=str(data.get("size_variant", "")),
            cached_at_iso=str(data.get("cached_at", "")),
            ttl_seconds=int(data.get("ttl_seconds", ttl_seconds)),
        )

    def image_bytes(self) -> bytes:
        return base64.b64decode(self.image_bytes_b64)


def default_ttl_seconds() -> int:
    """Look up TTL from settings; defaults to 7 days per FR-063."""
    try:
        days = int(get_settings().card_cache_ttl_days)
    except Exception:
        days = CARD_CACHE_DEFAULT_TTL_DAYS
    if days <= 0:
        days = CARD_CACHE_DEFAULT_TTL_DAYS
    return days * 24 * 3600


async def get_cached(
    redis_client: redis.Redis,
    user_id: str,
    jd_text: str,
    plan_hash: str,
) -> CardCacheEntry | None:
    """Read a cached card; returns ``None`` on miss or any error."""
    key = build_card_cache_key(user_id, jd_text, plan_hash)
    try:
        raw = await redis_client.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "card.cache.get_failed",
            extra={"cache_key": key, "error": str(exc)},
        )
        return None
    if raw is None:
        return None
    try:
        return CardCacheEntry.from_json(
            raw, user_id=user_id, ttl_seconds=default_ttl_seconds()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "card.cache.parse_failed",
            extra={"cache_key": key, "error": str(exc)},
        )
        return None


async def set_cached(
    redis_client: redis.Redis,
    entry: CardCacheEntry,
    *,
    ttl_seconds: int | None = None,
) -> bool:
    """Write a cached card with TTL; returns True on success."""
    try:
        await redis_client.set(
            entry.cache_key,
            entry.to_json(),
            ex=ttl_seconds if ttl_seconds is not None else default_ttl_seconds(),
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "card.cache.set_failed",
            extra={"cache_key": entry.cache_key, "error": str(exc)},
        )
        return False


async def invalidate(
    redis_client: redis.Redis,
    user_id: str,
    jd_text: str,
    plan_hash: str,
) -> bool:
    """Delete a cached card; returns True if a key was removed."""
    key = build_card_cache_key(user_id, jd_text, plan_hash)
    try:
        removed = await redis_client.delete(key)
        return bool(removed)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "card.cache.delete_failed",
            extra={"cache_key": key, "error": str(exc)},
        )
        return False


async def cache_stats(redis_client: redis.Redis) -> dict:
    """Return Redis stats for the card cache namespace.

    Used by the ``cache_stats`` CLI command (T083) — counts keys under
    the card_cache prefix and reports total memory used.
    """
    try:
        keys: list[bytes] = []
        async for key in redis_client.scan_iter(match=f"{CARD_CACHE_KEY_PREFIX}:*"):
            keys.append(key)
            if len(keys) >= 10_000:
                break
        n_keys = len(keys)
        memory_used = 0
        if n_keys:
            memory_used = sum(
                len(k) + len(await redis_client.memory_usage(k) or 0)
                for k in keys[:100]
            )
        return {
            "key_count": n_keys,
            "memory_used_bytes": memory_used,
            "ttl_seconds": default_ttl_seconds(),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("card.cache.stats_failed", extra={"error": str(exc)})
        return {"key_count": 0, "memory_used_bytes": 0, "error": str(exc)}


__all__ = [
    "CARD_CACHE_KEY_PREFIX",
    "CARD_CACHE_KEY_HEX_LENGTH",
    "CARD_CACHE_DEFAULT_TTL_DAYS",
    "CardCacheEntry",
    "build_card_cache_key",
    "cache_stats",
    "compute_plan_hash",
    "default_ttl_seconds",
    "get_cached",
    "invalidate",
    "set_cached",
]
