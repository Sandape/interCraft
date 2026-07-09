"""[REQ-048 US4 T084] Unit test for card cache.

Validates AC-22 / AC-24:
- Cache key formula matches the drill cache style:
    card_cache:{user_id}:{key_hex} with sha256(jd_text + plan_hash)[:32].
- 7-day TTL is honoured.
- Hit / miss semantics are correct.
- Cache is JSON-safe (image bytes are base64-enveloped).
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest

from app.services.card_renderer.cache import (
    CARD_CACHE_KEY_HEX_LENGTH,
    CARD_CACHE_KEY_PREFIX,
    CardCacheEntry,
    build_card_cache_key,
    compute_plan_hash,
    default_ttl_seconds,
)


USER_ID = "019ebc56-fb4f-7978-bf91-29abc5c13d93"


def _try_fakeredis():
    try:
        import fakeredis.aioredis as fakeredis
    except Exception:
        return None
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def redis_client():
    client = _try_fakeredis()
    if client is None:
        pytest.skip("fakeredis not installed")
    return client


# ---- AC-09c style: cache key formula ----


def test_card_cache_key_formula_sha256_32_chars() -> None:
    key = build_card_cache_key(USER_ID, "分布式事务 JD", "planhash123")
    parts = key.split(":")
    assert parts[0] == CARD_CACHE_KEY_PREFIX
    assert parts[1] == USER_ID
    key_hex = parts[2]
    assert len(key_hex) == CARD_CACHE_KEY_HEX_LENGTH
    assert len(key_hex) == 32
    # Total length: len("card_cache:") + 36 (uuid) + 1 (":") + 32 (hex) = 80
    assert len(key) == len("card_cache:") + 36 + 1 + 32


def test_card_cache_key_changes_with_jd_text() -> None:
    k1 = build_card_cache_key(USER_ID, "JD 1", "planhash")
    k2 = build_card_cache_key(USER_ID, "JD 2", "planhash")
    assert k1 != k2


def test_card_cache_key_changes_with_plan_hash() -> None:
    k1 = build_card_cache_key(USER_ID, "JD", "planv1")
    k2 = build_card_cache_key(USER_ID, "JD", "planv2")
    assert k1 != k2


def test_card_cache_key_stable_for_same_inputs() -> None:
    k1 = build_card_cache_key(USER_ID, "JD", "plan")
    k2 = build_card_cache_key(USER_ID, "JD", "plan")
    assert k1 == k2


# ---- AC-24: 7-day TTL ----


def test_default_ttl_seconds_is_7_days() -> None:
    """AC-24: card cache TTL = 7 days."""
    ttl = default_ttl_seconds()
    assert ttl == 7 * 24 * 3600


def test_compute_plan_hash_order_independent() -> None:
    """Dict-key ordering must not affect the hash (sort_keys=True)."""
    plan_a = {"a": 1, "b": 2, "c": 3}
    plan_b = {"c": 3, "a": 1, "b": 2}
    assert compute_plan_hash(plan_a) == compute_plan_hash(plan_b)


def test_compute_plan_hash_changes_on_field_change() -> None:
    h1 = compute_plan_hash({"a": 1, "b": 2})
    h2 = compute_plan_hash({"a": 1, "b": 3})
    assert h1 != h2


def test_compute_plan_hash_length_is_sha256() -> None:
    h = compute_plan_hash({"x": 1})
    assert len(h) == 64


# ---- AC-22: round-trip + hit semantics ----


async def test_cache_round_trip(redis_client) -> None:
    from app.services.card_renderer.cache import get_cached, set_cached

    jd_text = "字节跳动 分布式系统"
    plan_hash = compute_plan_hash({"a": 1, "b": 2})

    image_bytes = b"\xff\xd8\xff\xe0 fake jpeg " * 100
    entry = CardCacheEntry(
        user_id=USER_ID,
        cache_key=build_card_cache_key(USER_ID, jd_text, plan_hash),
        image_bytes_b64=base64.b64encode(image_bytes).decode("ascii"),
        sha256_hex="a" * 64,
        bytes_total=len(image_bytes),
        size_variant="4_3",
        cached_at_iso=datetime.now(UTC).isoformat(),
        ttl_seconds=default_ttl_seconds(),
    )

    # First read: miss.
    assert await get_cached(redis_client, USER_ID, jd_text, plan_hash) is None

    # Write.
    ok = await set_cached(redis_client, entry)
    assert ok is True

    # Second read: hit with bytes intact.
    cached = await get_cached(redis_client, USER_ID, jd_text, plan_hash)
    assert cached is not None
    assert cached.size_variant == "4_3"
    assert cached.bytes_total == len(image_bytes)
    assert cached.image_bytes() == image_bytes


async def test_cache_miss_on_different_jd(redis_client) -> None:
    """Same plan, different JD → cache miss."""
    from app.services.card_renderer.cache import get_cached, set_cached

    plan_hash = compute_plan_hash({"a": 1})

    entry = CardCacheEntry(
        user_id=USER_ID,
        cache_key=build_card_cache_key(USER_ID, "JD-1", plan_hash),
        image_bytes_b64=base64.b64encode(b"fake-jpg-1").decode("ascii"),
        sha256_hex="b" * 64,
        bytes_total=8,
        size_variant="4_3",
        cached_at_iso=datetime.now(UTC).isoformat(),
        ttl_seconds=default_ttl_seconds(),
    )
    await set_cached(redis_client, entry)

    # Different JD → miss.
    cached = await get_cached(redis_client, USER_ID, "JD-2", plan_hash)
    assert cached is None


async def test_cache_set_uses_7day_ttl(redis_client) -> None:
    """AC-24: TTL written by set_cached must be 7 days = 604800s."""
    from app.services.card_renderer.cache import get_cached, set_cached

    jd_text = "TTL check"
    plan_hash = compute_plan_hash({"ttl_test": True})

    entry = CardCacheEntry(
        user_id=USER_ID,
        cache_key=build_card_cache_key(USER_ID, jd_text, plan_hash),
        image_bytes_b64=base64.b64encode(b"x").decode("ascii"),
        sha256_hex="c" * 64,
        bytes_total=1,
        size_variant="4_3",
        cached_at_iso=datetime.now(UTC).isoformat(),
        ttl_seconds=default_ttl_seconds(),
    )
    await set_cached(redis_client, entry)

    ttl = await redis_client.ttl(entry.cache_key)
    # Redis TTL is in seconds; allow ±2s clock drift.
    assert abs(ttl - 7 * 24 * 3600) <= 2, f"TTL {ttl} != 7 days"


async def test_cache_set_degrades_when_redis_write_fails() -> None:
    """AC-22: cache write failures must not fail card generation."""
    from app.services.card_renderer.cache import set_cached

    class ReadOnlyRedis:
        async def set(self, *args, **kwargs):
            raise RuntimeError("read only replica")

    entry = CardCacheEntry(
        user_id=USER_ID,
        cache_key="card_cache:u:readonly",
        image_bytes_b64=base64.b64encode(b"x").decode("ascii"),
        sha256_hex="e" * 64,
        bytes_total=1,
        size_variant="4_3",
        cached_at_iso=datetime.now(UTC).isoformat(),
        ttl_seconds=default_ttl_seconds(),
    )

    assert await set_cached(ReadOnlyRedis(), entry) is False


def test_card_cache_entry_to_json_from_json_round_trip() -> None:
    entry = CardCacheEntry(
        user_id=USER_ID,
        cache_key="card_cache:u:abcd",
        image_bytes_b64=base64.b64encode(b"abc").decode("ascii"),
        sha256_hex="d" * 64,
        bytes_total=3,
        size_variant="4_3",
        cached_at_iso="2026-07-07T00:00:00+00:00",
        ttl_seconds=7 * 24 * 3600,
    )
    raw = entry.to_json()
    parsed = CardCacheEntry.from_json(raw, user_id=USER_ID, ttl_seconds=7 * 24 * 3600)
    assert parsed.user_id == entry.user_id
    assert parsed.cache_key == entry.cache_key
    assert parsed.sha256_hex == entry.sha256_hex
    assert parsed.bytes_total == entry.bytes_total
    assert parsed.size_variant == entry.size_variant
    assert parsed.image_bytes() == b"abc"
