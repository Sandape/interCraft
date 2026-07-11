"""Unit tests for query_jobs tool."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.agent.conversation.tools import query_jobs


def _job(**kw):
    return SimpleNamespace(
        id=uuid4(),
        company=kw.get("company", "腾讯"),
        position=kw.get("position", "后端"),
        status=kw.get("status", "applied"),
        deleted_at=None,
        interview_time=kw.get("interview_time"),
        base_location=kw.get("base_location", ""),
        jd_url=kw.get("jd_url"),
        status_history=kw.get("status_history", []),
        last_status_changed_at=kw.get(
            "last_status_changed_at", datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        ),
        updated_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_overview():
    session = AsyncMock()
    jobs = [
        _job(status="applied"),
        _job(company="字节", status="interview_1"),
        _job(company="阿里", status="passed"),
    ]
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=jobs)
        r = await query_jobs.execute(session, uuid4(), {})
    assert r["ok"]
    assert "求职概览" in r["reply_text"]
    assert "3" in r["reply_text"]


@pytest.mark.asyncio
async def test_empty():
    session = AsyncMock()
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=[])
        r = await query_jobs.execute(session, uuid4(), {})
    assert "还没有" in r["reply_text"]


@pytest.mark.asyncio
async def test_upcoming_none():
    session = AsyncMock()
    with patch("app.modules.jobs.service.JobService") as JS:
        JS.return_value.list = AsyncMock(return_value=[_job()])
        r = await query_jobs.execute(
            session, uuid4(), {"upcoming": True, "horizon_days": 7}
        )
    assert "暂无面试" in r["reply_text"]
