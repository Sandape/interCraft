"""Integration stubs for conversation → interview (REQ-054)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.orchestrator import ConversationOrchestrator


@pytest.mark.asyncio
async def test_start_interview_mutex_integration_stub():
    uid = uuid4()
    session = AsyncMock()
    active = SimpleNamespace(
        id=uuid4(), status="in_progress", company="字节", position="AI"
    )

    class Parser:
        async def parse(self, text, **kwargs):
            return {
                "intent": "start_interview",
                "entities": {"mode": "full", "general": True},
                "confidence": 0.9,
                "alternatives": [],
                "error": None,
            }

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
        patch(
            "app.modules.agent.conversation.interview.adapter.has_active_session",
            AsyncMock(return_value=active),
        ),
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=Parser())
        reply = await orch.handle(SimpleNamespace(text="开始模拟面试"))
    assert "进行中" in reply or "继续面试" in reply
