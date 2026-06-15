"""Integration test — Redis ping (no DB required)."""
import pytest

from app.core.redis import close_redis, redis_ping

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_redis_ping_succeeds():
    try:
        ok = await redis_ping()
    finally:
        await close_redis()
    # Local redis expected on 6379 in this environment.
    assert ok is True
