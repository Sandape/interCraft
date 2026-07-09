"""Unit tests for update_status tool."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.tools import update_status


def _job(**kw):
    return SimpleNamespace(
        id=kw.get("id", uuid4()),
        company=kw.get("company", "字节跳动"),
        position=kw.get("position", "AI应用"),
        status=kw.get("status", "applied"),
        deleted_at=None,
        updated_at="2026-07-09",
        interview_time=None,
    )


@pytest.mark.asyncio
async def test_prepare_missing_status():
    session = AsyncMock()
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=[_job()])
        r = await update_status.prepare(session, uuid4(), {"company": "字节"})
    assert r["error_code"] == "clarify"


@pytest.mark.asyncio
async def test_prepare_illegal_transition():
    session = AsyncMock()
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(
            return_value=[_job(status="interview_2")]
        )
        r = await update_status.prepare(
            session,
            uuid4(),
            {"company": "字节", "target_status": "interview_1"},
        )
    assert r["error_code"] == "invalid_status_transition"
    assert "无法" in r["reply_text"]


@pytest.mark.asyncio
async def test_prepare_interview_needs_time():
    session = AsyncMock()
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=[_job()])
        r = await update_status.prepare(
            session,
            uuid4(),
            {"company": "字节", "target_status": "interview_1"},
        )
    assert r["error_code"] == "clarify"
    assert "面试时间" in r["reply_text"]


@pytest.mark.asyncio
async def test_prepare_with_relative_time():
    session = AsyncMock()
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=[_job()])
        r = await update_status.prepare(
            session,
            uuid4(),
            {
                "company": "字节",
                "target_status": "interview_1",
                "interview_time_raw": "2026-07-13 14:00",
            },
        )
    assert r["ok"]
    assert r["data"]["needs_confirmation"]
    assert "一面" in r["reply_text"]


@pytest.mark.asyncio
async def test_normalize_status_aliases():
    assert update_status.normalize_status("挂了") == "failed"
    assert update_status.normalize_status("进一面") == "interview_1"
    assert update_status.normalize_status("过了") == "passed"
