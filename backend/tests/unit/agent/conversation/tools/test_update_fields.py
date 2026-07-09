"""Unit tests for update_fields tool."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.tools import update_fields


@pytest.mark.asyncio
async def test_reject_offer_fields():
    session = AsyncMock()
    r = await update_fields.prepare(
        session, uuid4(), {"company": "腾讯", "salary": "50k"}
    )
    assert r["error_code"] == "rejected_web_guide"
    assert "Web" in r["reply_text"]


@pytest.mark.asyncio
async def test_prepare_location():
    session = AsyncMock()
    job = SimpleNamespace(
        id=uuid4(),
        company="阿里",
        position="Java",
        status="applied",
        deleted_at=None,
        updated_at="x",
    )
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=[job])
        r = await update_fields.prepare(
            session,
            uuid4(),
            {"company": "阿里", "base_location": "杭州"},
        )
    assert r["ok"]
    assert r["data"]["pending_action"]["type"] == "update_job_fields"
    assert r["data"]["pending_action"]["params"]["base_location"] == "杭州"


@pytest.mark.asyncio
async def test_execute_patch():
    session = AsyncMock()
    jid = uuid4()
    job = SimpleNamespace(id=jid, company="阿里", position="Java")
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.patch = AsyncMock(return_value=job)
        r = await update_fields.execute(
            session,
            uuid4(),
            {"job_id": str(jid), "base_location": "杭州"},
        )
    assert r["ok"]
    assert "杭州" in r["reply_text"]
