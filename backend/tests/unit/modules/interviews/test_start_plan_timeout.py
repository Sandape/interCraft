from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.interviews.service import InterviewSessionService


@pytest.mark.asyncio
async def test_start_full_plan_prewarm_timeout_returns_failed_status() -> None:
    sid = uuid4()
    uid = uuid4()
    session = SimpleNamespace(
        id=sid,
        mode="full",
        status="pending",
        interview_plan=None,
        plan_status=None,
        plan_error_code=None,
        plan_error_message=None,
        degraded=False,
        web_research=None,
        position="AI Engineer",
        company="DemoCo",
        thread_id=None,
        branch_id=None,
        job_id=None,
        max_questions=10,
        error_question_ids=None,
    )
    svc = InterviewSessionService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.get = AsyncMock(return_value=session)
    svc.repo.update_status = AsyncMock()
    svc.repo.update_plan_lifecycle = AsyncMock()
    svc._ensure_plan = AsyncMock(side_effect=TimeoutError)
    svc._invalidate_dashboard = AsyncMock()

    out = await svc.start(sid, uid)

    assert out["status"] == "in_progress"
    assert out["plan_status"] == "failed"
    assert out["plan_error_code"] == "PLAN_PREWARM_TIMEOUT"
    assert out["degraded"] is False
    svc.repo.update_plan_lifecycle.assert_awaited_once()
