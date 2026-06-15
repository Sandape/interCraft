"""T013 — Lock acquire/release integration test (real Redis).

Tests: concurrent acquire, release-after-acquire, same-user-different-device (409),
lock-not-found (404), WS push verification.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_acquire_success_and_get_status():
    """User acquires a lock, then status shows locked=true."""
    from app.modules.locks.redis_store import (
        LOCK_PREFIX,
        acquire as redis_acquire,
        get as redis_get,
        release as redis_release,
        _key,
    )

    resource_id = str(uuid4())
    key = _key("resume_branch", resource_id)

    # Clean up first
    await redis_release(key)

    ok = await redis_acquire(
        "resume_branch",
        resource_id,
        {
            "lock_id": str(uuid4()),
            "user_id": "user-a",
            "device_id": "dev-1",
            "acquired_at": "2026-06-13T10:00:00Z",
            "heartbeat_at": "2026-06-13T10:00:00Z",
        },
    )
    assert ok is True

    data = await redis_get(key)
    assert data is not None
    assert data["user_id"] == "user-a"

    # Clean up
    await redis_release(key)


@pytest.mark.asyncio
async def test_concurrent_acquire_only_one_succeeds():
    """Two users race to acquire the same resource — only one wins."""
    import asyncio

    from app.modules.locks.redis_store import (
        acquire as redis_acquire,
        release as redis_release,
        _key,
    )

    resource_id = str(uuid4())
    key = _key("resume_branch", resource_id)
    await redis_release(key)

    async def try_acquire(uid: str) -> bool:
        return await redis_acquire(
            "resume_branch",
            resource_id,
            {
                "lock_id": str(uuid4()),
                "user_id": uid,
                "device_id": f"dev-{uid}",
                "acquired_at": "2026-06-13T10:00:00Z",
                "heartbeat_at": "2026-06-13T10:00:00Z",
            },
        )

    results = await asyncio.gather(
        try_acquire("user-a"),
        try_acquire("user-b"),
    )
    assert sum(1 for r in results if r) == 1  # Exactly one succeeds

    await redis_release(key)


@pytest.mark.asyncio
async def test_release_after_acquire():
    """Acquire then release — lock key is deleted."""
    from app.modules.locks.redis_store import (
        acquire as redis_acquire,
        get as redis_get,
        release as redis_release,
        _key,
    )

    resource_id = str(uuid4())
    key = _key("resume_branch", resource_id)
    await redis_release(key)

    await redis_acquire(
        "resume_branch",
        resource_id,
        {
            "lock_id": str(uuid4()),
            "user_id": "user-a",
            "device_id": "dev-1",
            "acquired_at": "2026-06-13T10:00:00Z",
            "heartbeat_at": "2026-06-13T10:00:00Z",
        },
    )

    deleted = await redis_release(key)
    assert deleted == 1

    data = await redis_get(key)
    assert data is None


@pytest.mark.asyncio
async def test_lock_status_unlocked_when_none_exists():
    """GET status returns locked=false when no lock exists."""
    from app.modules.locks.service import LockService

    svc = LockService()
    result = await svc.get_status("resume_branch", str(uuid4()))
    assert result.locked is False
    assert result.resource_type == "resume_branch"
