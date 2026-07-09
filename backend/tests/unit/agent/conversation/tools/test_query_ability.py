"""Unit tests for query_ability tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.tools import query_ability


@pytest.mark.asyncio
async def test_empty_dashboard():
    session = AsyncMock()
    with (
        patch("app.modules.ability_profile.repository.AbilityProfileRepository"),
        patch("app.modules.ability_profile.service.AbilityProfileService") as S,
    ):
        S.return_value.get_dashboard = AsyncMock(return_value={"dimensions": []})
        r = await query_ability.execute(session, uuid4(), {})
    assert "还没有能力画像" in r["reply_text"]


@pytest.mark.asyncio
async def test_with_dimensions():
    session = AsyncMock()
    dims = [
        {"key": "algo", "label_zh": "算法", "actual_score": 6.0, "trend": "down"},
        {"key": "eng", "label_zh": "工程实践", "actual_score": 8.5, "trend": "up"},
    ]
    with (
        patch("app.modules.ability_profile.repository.AbilityProfileRepository"),
        patch("app.modules.ability_profile.service.AbilityProfileService") as S,
    ):
        S.return_value.get_dashboard = AsyncMock(
            return_value={"dimensions": dims}
        )
        r = await query_ability.execute(session, uuid4(), {})
    assert r["ok"]
    assert "能力画像" in r["reply_text"]
    assert "工程实践" in r["reply_text"]
