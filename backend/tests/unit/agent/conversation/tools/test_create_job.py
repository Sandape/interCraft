"""Unit tests for create_job tool."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.tools import create_job


@pytest.mark.asyncio
async def test_prepare_missing_position():
    session = AsyncMock()
    r = await create_job.prepare(session, uuid4(), {"company": "阿里"})
    assert r["error_code"] == "clarify"
    assert "职位" in r["reply_text"]


@pytest.mark.asyncio
async def test_prepare_ok_pending():
    session = AsyncMock()
    r = await create_job.prepare(
        session, uuid4(), {"company": "腾讯", "position": "后端开发工程师"}
    )
    assert r["ok"]
    assert r["data"]["needs_confirmation"]
    assert r["data"]["pending_action"]["type"] == "create_job"
    assert "确认" in r["reply_text"]


@pytest.mark.asyncio
async def test_execute_success():
    session = AsyncMock()
    job = SimpleNamespace(id=uuid4(), company="腾讯", position="后端")
    with patch(
        "app.modules.jobs.service.JobService"
    ) as JS:
        JS.return_value.create = AsyncMock(return_value=job)
        r = await create_job.execute(
            session, uuid4(), {"company": "腾讯", "position": "后端"}
        )
    assert r["ok"]
    assert "已创建" in r["reply_text"]
