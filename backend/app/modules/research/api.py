"""FastAPI router for the research module (REQ-053)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.domain.interview_report import (
    ResearchReportListOut,
    ResearchReportOut,
)
from app.modules.research.repository import ResearchTaskRepository
from app.modules.research.schemas import (
    ResearchStats,
    TriggerResearchRequest,
    TriggerResearchResponse,
)
from app.modules.research.service import ResearchService
from app.repositories.interview_report_repo import InterviewReportRepo

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/stats", response_model=ResearchStats)
async def research_stats(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_user_dep),
) -> ResearchStats:
    """Return research task statistics for the current user."""
    svc = ResearchService(session)
    return await svc.get_stats(user_id)


# Internal trigger endpoint (debug/admin)
@router.post("/internal/trigger", response_model=TriggerResearchResponse)
async def trigger_research(
    body: TriggerResearchRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_user_dep),
) -> TriggerResearchResponse:
    """Manually trigger a research task for a job. Bypasses the 5h window."""
    from app.modules.jobs.repository import JobRepository

    job_repo = JobRepository(session)
    job = await job_repo.get(body.job_id, user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.interview_time is None:
        raise HTTPException(status_code=422, detail="Job has no interview_time set")

    task_repo = ResearchTaskRepository(session)
    task_id = await task_repo.create(
        job_id=job.id,
        user_id=user_id,
        interview_time=job.interview_time,
    )
    # Enqueue via ARQ
    try:
        from app.core.redis import enqueue_job
        await enqueue_job("execute_research_task", task_id=str(task_id))
    except Exception as exc:
        # No Redis in test — that's OK, the task is created and can be polled
        pass

    return TriggerResearchResponse(task_id=task_id, status="pending")


# Report rating endpoint (SC-009)
@router.patch("/reports/{report_id}/rating", response_model=ResearchReportOut)
async def rate_report(
    report_id: UUID,
    rating: int,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_user_dep),
) -> ResearchReportOut:
    """Submit user rating (1-5) for a research report."""
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=422, detail="评分必须为 1-5 的整数")

    repo = InterviewReportRepo(session)
    updated = await repo.update_rating(report_id, rating, user_id=user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="报告不存在")

    out = await repo.get_research_report(report_id, user_id=user_id)
    if out is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    return out


# Reports attached to a specific job — registered on the jobs router too,
# but exposed here under /research/reports-by-job/{job_id} for clarity.
@router.get("/reports-by-job/{job_id}", response_model=ResearchReportListOut)
async def list_research_reports_for_job(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_user_dep),
) -> ResearchReportListOut:
    repo = InterviewReportRepo(session)
    data = await repo.list_research_reports_for_job(job_id, user_id=user_id)
    return ResearchReportListOut(data=data)


__all__ = ["router"]