"""Unit tests for query_reports tool."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.tools import query_reports


@pytest.mark.asyncio
async def test_no_reports():
    session = AsyncMock()
    with patch("app.modules.interviews.service.InterviewSessionService") as S:
        S.return_value.list = AsyncMock(return_value=[])
        r = await query_reports.execute(session, uuid4(), {})
    assert "还没有完成" in r["reply_text"]


@pytest.mark.asyncio
async def test_with_completed():
    session = AsyncMock()
    sess = SimpleNamespace(
        id=uuid4(),
        company="字节",
        position="AI",
        status="completed",
        overall_score=7.5,
        ended_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    with patch("app.modules.interviews.service.InterviewSessionService") as S:
        inst = S.return_value
        inst.list = AsyncMock(return_value=[sess])
        inst.get_report = AsyncMock(
            return_value={
                "overall_score": 7.5,
                "dimension_scores": {"算法": 6.0, "工程实践": 8.5},
                "improvements": ["加强动态规划"],
            }
        )
        r = await query_reports.execute(session, uuid4(), {"latest_only": True})
    assert r["ok"]
    assert "7.5" in r["reply_text"]
