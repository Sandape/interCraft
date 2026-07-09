"""Integration stubs for conversation → jobs (REQ-054).

Full DB integration is covered when test DB + Redis are available.
These tests verify wiring with mocks at the service boundary.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.orchestrator import ConversationOrchestrator


@pytest.mark.asyncio
async def test_create_job_confirm_flow_integration_stub():
    uid = uuid4()
    session = AsyncMock()
    stored = {
        "state": "idle",
        "pending_action": None,
        "queued_after_confirm": [],
        "unknown_streak": 0,
        "last_active_at": "x",
    }

    async def _get(_):
        return dict(stored)

    async def _set(_, ctx):
        stored.clear()
        stored.update({k: v for k, v in ctx.items() if not str(k).startswith("_")})

    class Parser:
        async def parse(self, text, **kwargs):
            return {
                "intent": "create_job",
                "entities": {"company": "腾讯", "position": "后端"},
                "confidence": 0.95,
                "alternatives": [],
                "error": None,
            }

    with (
        patch("app.modules.agent.conversation.orchestrator.get_context", _get),
        patch("app.modules.agent.conversation.orchestrator.set_context", _set),
        patch("app.modules.agent.conversation.context_store.set_context", _set),
    ):
        orch = ConversationOrchestrator(session, uid, intent_parser=Parser())
        reply1 = await orch.handle(SimpleNamespace(text="新增岗位：腾讯，后端"))
        assert "确认" in reply1
        assert stored["state"] == "awaiting_confirmation"

        job = SimpleNamespace(id=uuid4(), company="腾讯", position="后端")
        with patch("app.modules.jobs.service.JobService") as JS:
            JS.return_value.create = AsyncMock(return_value=job)
            reply2 = await orch.handle(SimpleNamespace(text="确认"))
        assert "已创建" in reply2
        assert stored["state"] == "idle"
