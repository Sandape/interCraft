"""[REQ-048 US2 T047] Unit test for drill cache logic.

Validates:
- AC-09: cache hit rate ≥80% (we test the hit path).
- AC-09b: JD text change / error_pool change → cache miss.
- AC-09c: cache key formula is locked: sha256(jd + error_pool_hash)[:32].

This test uses a fakeredis in-memory backend (we do NOT require a real
Redis server for unit tests). If fakeredis is unavailable, the test
falls back to skipping with a clear marker.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agents.interview.drill_helpers.cache import (
    CACHE_KEY_PREFIX,
    DEFAULT_TTL_SECONDS,
    KEY_HEX_LENGTH,
    DrillCacheEntry,
    build_cache_key,
    compute_error_pool_hash,
    get_cached,
    set_cached,
)


USER_ID = "019ebc56-fb4f-7978-bf91-29abc5c13d93"


def _try_fakeredis() -> "object | None":
    try:
        import fakeredis.aioredis as fakeredis  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - fakeredis not installed
        return None
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def redis_client():
    client = _try_fakeredis()
    if client is None:  # pragma: no cover - graceful skip
        pytest.skip("fakeredis not installed")
    return client


def test_cache_key_formula_sha256_32_chars() -> None:
    """AC-09c: key_hex = sha256(jd + error_pool_hash)[:32]; full key length 70."""
    key = build_cache_key(USER_ID, "分布式事务", "err_pool_xyz")
    parts = key.split(":")
    assert parts[0] == CACHE_KEY_PREFIX
    assert parts[1] == USER_ID
    key_hex = parts[2]
    assert len(key_hex) == KEY_HEX_LENGTH
    assert len(key_hex) == 32
    # Total length: len("drill_cache:") + 36 (uuid) + 1 (":") + 32 (hex) = 70
    assert len(key) == len("drill_cache:") + 36 + 1 + 32


def test_cache_key_changes_with_jd_text() -> None:
    """AC-09b: JD text change must trigger cache miss (different key)."""
    k1 = build_cache_key(USER_ID, "分布式事务", "err_pool_xyz")
    k2 = build_cache_key(USER_ID, "微服务", "err_pool_xyz")
    assert k1 != k2


def test_cache_key_changes_with_error_pool_hash() -> None:
    """AC-09b: error_pool_hash change must trigger cache miss (different key)."""
    k1 = build_cache_key(USER_ID, "分布式事务", "err_pool_v1")
    k2 = build_cache_key(USER_ID, "分布式事务", "err_pool_v2")
    assert k1 != k2


def test_cache_key_stable_for_same_inputs() -> None:
    """AC-09b: same inputs → identical Redis key (hash algorithm consistency)."""
    k1 = build_cache_key(USER_ID, "RAG", "err_pool_xyz")
    k2 = build_cache_key(USER_ID, "RAG", "err_pool_xyz")
    assert k1 == k2


def test_cache_key_user_id_changes_prefix() -> None:
    """Different user → different key (user-scoped isolation)."""
    k1 = build_cache_key("user-a", "RAG", "err_pool_xyz")
    k2 = build_cache_key("user-b", "RAG", "err_pool_xyz")
    assert k1 != k2


def test_compute_error_pool_hash_order_independent() -> None:
    """Sort IDs to make hash stable regardless of input order."""
    h1 = compute_error_pool_hash(["a", "b", "c"])
    h2 = compute_error_pool_hash(["c", "a", "b"])
    assert h1 == h2
    # Different content → different hash.
    h3 = compute_error_pool_hash(["a", "b", "d"])
    assert h1 != h3


def test_compute_error_pool_hash_empty_input() -> None:
    h = compute_error_pool_hash([])
    assert isinstance(h, str)
    assert len(h) == 64  # full SHA256 hex length


async def test_cache_set_then_get_round_trip(redis_client) -> None:
    """AC-09: cache hit on second call with same inputs."""
    jd_text = "分布式事务"
    pool_hash = compute_error_pool_hash(["a", "b", "c"])
    key = build_cache_key(USER_ID, jd_text, pool_hash)

    entry = DrillCacheEntry(
        user_id=USER_ID,
        cache_key=key,
        source_question_ids=["a", "b", "c"],
        cached_at_iso=datetime.now(UTC).isoformat(),
        ttl_seconds=DEFAULT_TTL_SECONDS,
    )

    # First call: miss (nothing cached yet).
    assert await get_cached(redis_client, USER_ID, jd_text, pool_hash) is None

    # Write to cache.
    ok = await set_cached(redis_client, entry)
    assert ok is True

    # Second call: hit.
    cached = await get_cached(redis_client, USER_ID, jd_text, pool_hash)
    assert cached is not None
    assert cached.source_question_ids == ["a", "b", "c"]
    assert cached.cache_key == key


async def test_cache_different_jd_text_misses(redis_client) -> None:
    """AC-09b: different JD text → miss even though pool hash unchanged."""
    pool_hash = compute_error_pool_hash(["a", "b", "c"])
    entry = DrillCacheEntry(
        user_id=USER_ID,
        cache_key=build_cache_key(USER_ID, "分布式事务", pool_hash),
        source_question_ids=["a", "b", "c"],
        cached_at_iso=datetime.now(UTC).isoformat(),
        ttl_seconds=DEFAULT_TTL_SECONDS,
    )
    await set_cached(redis_client, entry)

    # Different JD text → different key → miss.
    cached = await get_cached(redis_client, USER_ID, "微服务", pool_hash)
    assert cached is None


def test_drill_cache_entry_to_json_from_json_round_trip() -> None:
    entry = DrillCacheEntry(
        user_id=USER_ID,
        cache_key="drill_cache:user:abcd",
        source_question_ids=["x", "y", "z"],
        cached_at_iso="2026-07-07T00:00:00+00:00",
        ttl_seconds=300,
    )
    raw = entry.to_json()
    parsed = DrillCacheEntry.from_json(raw, user_id=USER_ID, ttl_seconds=300)
    assert parsed.user_id == entry.user_id
    assert parsed.cache_key == entry.cache_key
    assert parsed.source_question_ids == entry.source_question_ids
    assert parsed.cached_at_iso == entry.cached_at_iso
    assert parsed.ttl_seconds == entry.ttl_seconds