"""Plan prewarm service tests (REQ-058 T021) — unit with mocks."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.llm_client import QuotaExceededError
from app.modules.interviews.service import InterviewSessionService


@pytest.mark.asyncio
async def test_ensure_plan_reuses_ready() -> None:
    sid = uuid4()
    uid = uuid4()
    session = SimpleNamespace(
        id=sid,
        mode="full",
        interview_plan={
            "focus_areas": [{"area": "a", "weight": 1}],
            "suggested_questions": ["q1"],
        },
        plan_status="ready",
        plan_error_code=None,
        plan_error_message=None,
        degraded=False,
        web_research=None,
        position="后端",
        company="美团",
        thread_id=str(sid),
        branch_id=None,
        job_id=None,
        max_questions=10,
        error_question_ids=None,
    )
    svc = InterviewSessionService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.get = AsyncMock(return_value=session)
    svc.repo.update_plan_lifecycle = AsyncMock()

    out = await svc._ensure_plan(sid, uid)
    assert out["plan_status"] == "ready"
    svc.repo.update_plan_lifecycle.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_plan_quota_sets_failed() -> None:
    sid = uuid4()
    uid = uuid4()
    session = SimpleNamespace(
        id=sid,
        mode="full",
        interview_plan=None,
        plan_status=None,
        plan_error_code=None,
        plan_error_message=None,
        degraded=False,
        web_research=None,
        position="后端",
        company="美团",
        thread_id=str(sid),
        branch_id=None,
        job_id=None,
        max_questions=10,
        error_question_ids=None,
    )
    svc = InterviewSessionService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.get = AsyncMock(return_value=session)
    svc.repo.update_plan_lifecycle = AsyncMock()
    svc.generate_plan = AsyncMock(side_effect=QuotaExceededError(used=1, quota=1, estimated=100))

    out = await svc._ensure_plan(sid, uid)
    assert out["plan_status"] == "failed"
    assert out["plan_error_code"] == "QUOTA_EXCEEDED"
    assert "额度" in (out["plan_error_message"] or "")
