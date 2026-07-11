"""Unit tests for interview adapter (mocked services)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.interview.adapter import InterviewAdapter


@pytest.mark.asyncio
async def test_start_mutex_blocked():
    session = AsyncMock()
    uid = uuid4()
    active = SimpleNamespace(
        id=uuid4(), status="in_progress", company="字节", position="AI"
    )
    with patch(
        "app.modules.agent.conversation.interview.adapter.has_active_session",
        AsyncMock(return_value=active),
    ):
        adapter = InterviewAdapter(session, uid)
        r = await adapter.start({"mode": "full", "general": True})
    assert r["error_code"] == "mutex_blocked"
    assert "继续面试" in r["reply_text"]


@pytest.mark.asyncio
async def test_start_clarify_mode():
    session = AsyncMock()
    with patch(
        "app.modules.agent.conversation.interview.adapter.has_active_session",
        AsyncMock(return_value=None),
    ):
        adapter = InterviewAdapter(session, uuid4())
        r = await adapter.start({})
    assert r["ok"]
    assert "面试模式" in r["reply_text"]


@pytest.mark.asyncio
async def test_pause_and_end():
    session = AsyncMock()
    uid = uuid4()
    sid = uuid4()
    adapter = InterviewAdapter(session, uid)
    with patch(
        "app.modules.interviews.repository.InterviewSessionRepository"
    ) as R:
        R.return_value.get = AsyncMock(
            return_value=SimpleNamespace(id=sid, status="in_progress")
        )
        R.return_value.update_status = AsyncMock()
        pause = await adapter.pause(sid, 2)
        assert "暂停" in pause["reply_text"]

        end = await adapter.end(sid, 2)
    assert end["ok"]
    assert "结束" in end["reply_text"]
    # rounds < 3 → expired
    assert end["data"]["status"] == "expired"


@pytest.mark.asyncio
async def test_submit_answer_formats_reply():
    session = AsyncMock()
    uid = uuid4()
    sid = uuid4()
    with patch("app.modules.interviews.service.InterviewSessionService") as S:
        S.return_value.submit_answer = AsyncMock(
            return_value={
                "scores": [{"score": 8, "feedback": "表达清晰"}],
                "next_question": "请谈谈并发控制",
            }
        )
        adapter = InterviewAdapter(session, uid)
        # Force fast path by patching wait to return immediately — submit is mocked fast
        r = await adapter.submit_answer(sid, "我的回答", 1)
    assert r["ok"]
    assert "8" in r["reply_text"] or "得分" in r["reply_text"]
