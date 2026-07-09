"""Unit tests for interview mutex."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.interview.mutex import has_active_session


@pytest.mark.asyncio
async def test_no_active():
    session = AsyncMock()
    with patch(
        "app.modules.interviews.repository.InterviewSessionRepository"
    ) as R:
        R.return_value.list = AsyncMock(return_value=[])
        assert await has_active_session(session, uuid4()) is None


@pytest.mark.asyncio
async def test_finds_in_progress():
    session = AsyncMock()
    active = SimpleNamespace(id=uuid4(), status="in_progress", company="字节")

    async def _list(user_id, *, status=None, limit=50):
        if status == "in_progress":
            return [active]
        return []

    with patch(
        "app.modules.interviews.repository.InterviewSessionRepository"
    ) as R:
        R.return_value.list = _list
        found = await has_active_session(session, uuid4())
    assert found is active
