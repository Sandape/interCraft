"""Unit tests for ConversationOrchestrator meta flows (help / unknown / confirm)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.intent_parser import IntentParser
from app.modules.agent.conversation.orchestrator import ConversationOrchestrator
from app.modules.agent.conversation.reply_formatter import HELP_TEXT, UNKNOWN_STREAK_TEXT


class _FakeParser(IntentParser):
    def __init__(self, results: list[dict]):
        super().__init__(llm_client=AsyncMock())
        self._results = list(results)

    async def parse(self, text, *, user_id, thread_id=None, skip_confirm_rules=False):
        if not self._results:
            return {
                "intent": "unknown",
                "entities": {},
                "confidence": 0.0,
                "alternatives": [],
                "error": None,
            }
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_help_intent():
    uid = uuid4()
    session = AsyncMock()
    parser = _FakeParser(
        [{"intent": "help", "entities": {}, "confidence": 1.0, "alternatives": [], "error": None}]
    )
    ctx = {
        "state": "idle",
        "pending_action": None,
        "queued_after_confirm": [],
        "unknown_streak": 0,
        "last_active_at": "2026-07-09T00:00:00+00:00",
    }
    with (
        patch(
            "app.modules.agent.conversation.orchestrator.get_context",
            AsyncMock(return_value=dict(ctx)),
        ),
        patch(
            "app.modules.agent.conversation.orchestrator.set_context",
            AsyncMock(),
        ),
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=parser)
        reply = await orch.handle(SimpleNamespace(text="帮助"))
    assert "岗位" in reply or reply == HELP_TEXT


@pytest.mark.asyncio
async def test_unknown_streak_escalates():
    uid = uuid4()
    session = AsyncMock()
    results = [
        {"intent": "unknown", "entities": {}, "confidence": 0.1, "alternatives": [], "error": None}
        for _ in range(3)
    ]
    parser = _FakeParser(results)
    stored = {
        "state": "idle",
        "pending_action": None,
        "queued_after_confirm": [],
        "unknown_streak": 2,
        "last_active_at": "2026-07-09T00:00:00+00:00",
    }

    async def _get(_uid):
        return dict(stored)

    async def _set(_uid, ctx):
        stored.update(ctx)

    with (
        patch(
            "app.modules.agent.conversation.orchestrator.get_context",
            _get,
        ),
        patch(
            "app.modules.agent.conversation.orchestrator.set_context",
            _set,
        ),
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=parser)
        reply = await orch.handle(SimpleNamespace(text="今天天气怎么样"))
    assert "InterCraft" in reply or reply == UNKNOWN_STREAK_TEXT


@pytest.mark.asyncio
async def test_awaiting_confirmation_requires_confirm_word():
    uid = uuid4()
    session = AsyncMock()
    stored = {
        "state": "awaiting_confirmation",
        "pending_action": {
            "type": "create_job",
            "params": {"company": "腾讯", "position": "后端"},
        },
        "queued_after_confirm": [],
        "unknown_streak": 0,
        "last_active_at": "2026-07-09T00:00:00+00:00",
    }

    async def _get(_):
        return dict(stored)

    async def _set(_, ctx):
        stored.clear()
        stored.update(ctx)

    with (
        patch("app.modules.agent.conversation.orchestrator.get_context", _get),
        patch("app.modules.agent.conversation.orchestrator.set_context", _set),
        patch(
            "app.modules.agent.conversation.orchestrator.tool_create_job.execute",
            AsyncMock(
                return_value={
                    "ok": True,
                    "reply_text": "✅ 已创建：腾讯 · 后端（已投递）。",
                    "data": {},
                    "error_code": None,
                }
            ),
        ) as exec_mock,
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=_FakeParser([]))
        # Non-confirm while awaiting
        reply1 = await orch.handle(SimpleNamespace(text="顺便查一下进展"))
        assert "确认" in reply1
        exec_mock.assert_not_awaited()

        # Confirm
        reply2 = await orch.handle(SimpleNamespace(text="确认"))
        assert "已创建" in reply2
        exec_mock.assert_awaited_once()
        assert stored["state"] == "idle"


@pytest.mark.asyncio
async def test_cancel_clears_pending():
    uid = uuid4()
    session = AsyncMock()
    stored = {
        "state": "awaiting_confirmation",
        "pending_action": {"type": "create_job", "params": {"company": "A", "position": "B"}},
        "queued_after_confirm": [],
        "unknown_streak": 0,
        "last_active_at": "2026-07-09T00:00:00+00:00",
    }

    async def _get(_):
        return dict(stored)

    async def _set(_, ctx):
        stored.clear()
        stored.update(ctx)

    with (
        patch("app.modules.agent.conversation.orchestrator.get_context", _get),
        patch("app.modules.agent.conversation.orchestrator.set_context", _set),
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=_FakeParser([]))
        reply = await orch.handle(SimpleNamespace(text="取消"))
    assert "取消" in reply
    assert stored["state"] == "idle"
    assert stored["pending_action"] is None


@pytest.mark.asyncio
async def test_rejected_web_guide():
    uid = uuid4()
    session = AsyncMock()
    parser = _FakeParser(
        [
            {
                "intent": "rejected_web_guide",
                "entities": {"guide": "delete", "reply": "删除请用 Web"},
                "confidence": 0.9,
                "alternatives": [],
                "error": None,
            }
        ]
    )
    with (
        patch(
            "app.modules.agent.conversation.orchestrator.get_context",
            AsyncMock(
                return_value={
                    "state": "idle",
                    "pending_action": None,
                    "queued_after_confirm": [],
                    "unknown_streak": 0,
                    "last_active_at": "x",
                }
            ),
        ),
        patch(
            "app.modules.agent.conversation.orchestrator.set_context",
            AsyncMock(),
        ),
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=parser)
        reply = await orch.handle(SimpleNamespace(text="删掉岗位"))
    assert "Web" in reply
