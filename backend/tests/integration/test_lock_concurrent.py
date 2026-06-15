"""T052 — Lock concurrent acquire serializable test.

Verifies SET NX atomicity: 2 concurrent acquires on the same resource
result in exactly 1 success.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_concurrent_acquire_atomicity():
    """Two coroutines race for the same lock — exactly one wins."""
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

    # Launch 3 concurrent acquires
    results = await asyncio.gather(
        try_acquire("user-a"),
        try_acquire("user-b"),
        try_acquire("user-c"),
    )
    success_count = sum(1 for r in results if r)
    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"

    await redis_release(key)
