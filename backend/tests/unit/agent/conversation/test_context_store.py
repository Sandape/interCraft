"""Unit tests for conversation context_store."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.context_store import (
    KEY_PREFIX,
    TTL_SECONDS,
    RedisUnavailableError,
    clear_context,
    default_context,
    get_context,
    set_context,
)


@pytest.mark.asyncio
async def test_get_context_miss_returns_idle_default():
    user_id = uuid4()
    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)
    with patch(
        "app.modules.agent.conversation.context_store.get_redis",
        return_value=mock_r,
    ):
        ctx = await get_context(user_id)
    assert ctx["state"] == "idle"
    assert ctx["pending_action"] is None
    assert ctx["unknown_streak"] == 0


@pytest.mark.asyncio
async def test_set_and_get_roundtrip():
    user_id = uuid4()
    store: dict[str, str] = {}

    mock_r = AsyncMock()

    async def _get(key):
        return store.get(key)

    async def _set(key, value, ex=None):
        store[key] = value
        assert ex == TTL_SECONDS

    mock_r.get = _get
    mock_r.set = _set

    with patch(
        "app.modules.agent.conversation.context_store.get_redis",
        return_value=mock_r,
    ):
        await set_context(
            user_id,
            {
                "state": "awaiting_confirmation",
                "pending_action": {"type": "create_job", "params": {"company": "腾讯"}},
                "unknown_streak": 0,
            },
        )
        ctx = await get_context(user_id)

    assert ctx["state"] == "awaiting_confirmation"
    assert ctx["pending_action"]["type"] == "create_job"
    assert store[f"{KEY_PREFIX}{user_id}"]


@pytest.mark.asyncio
async def test_redis_error_raises_unavailable():
    user_id = uuid4()
    mock_r = AsyncMock()
    mock_r.get = AsyncMock(side_effect=ConnectionError("down"))
    with patch(
        "app.modules.agent.conversation.context_store.get_redis",
        return_value=mock_r,
    ):
        with pytest.raises(RedisUnavailableError):
            await get_context(user_id)


@pytest.mark.asyncio
async def test_clear_context():
    user_id = uuid4()
    mock_r = AsyncMock()
    mock_r.delete = AsyncMock(return_value=1)
    with patch(
        "app.modules.agent.conversation.context_store.get_redis",
        return_value=mock_r,
    ):
        await clear_context(user_id)
    mock_r.delete.assert_awaited_once()


def test_default_context_shape():
    ctx = default_context()
    assert set(ctx.keys()) >= {
        "state",
        "pending_action",
        "queued_after_confirm",
        "unknown_streak",
        "last_active_at",
    }
