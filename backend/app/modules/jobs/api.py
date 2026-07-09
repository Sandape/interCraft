"""Jobs API (M10) — 7 endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, db_session_user_dep
from app.core.db import get_db_session
from app.domain.enums import JOB_TRANSITIONS
from app.modules.jobs.schemas import (
    CreateJobInput, JobListOut, JobOut, JobStatsOut, JobTimelineOut,
    PatchJobInput, TransitionEdge, TransitionsOut, UpdateJobStatusInput,
)
from app.modules.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> JobService:
    return JobService(session)


@router.get("/transitions", response_model=TransitionsOut)
async def job_transitions(
    user_id: UUID = Depends(get_current_user_id),
) -> TransitionsOut:
    """Expose the canonical JOB_TRANSITIONS graph as a flat list of edges.

    Registered BEFORE the `/{id}` route so the literal path matches first.
    The response is a static read of the in-process enum; safe to cache.
    """
    statuses = list(JOB_TRANSITIONS.keys())
    transitions: list[TransitionEdge] = []
    for from_, tos in JOB_TRANSITIONS.items():
        for to in sorted(tos):
            transitions.append(TransitionEdge(**{"from": from_, "to": to}))
    return TransitionsOut(statuses=statuses, transitions=transitions)


@router.get("", response_model=JobListOut)
async def list_jobs(
    status: str | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> dict:
    data = await svc.list(user_id, status=status, branch_id=branch_id, limit=limit)
    return {"data": data, "next_cursor": None, "has_more": len(data) >= limit}


@router.post("", status_code=201, response_model=JobOut)
async def create_job(
    body: CreateJobInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> JobOut:
    return await svc.create(user_id, body.model_dump(exclude_none=True))


@router.get("/stats", response_model=JobStatsOut)
async def job_stats(
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> dict:
    return await svc.stats(user_id)


@router.get("/{id}", response_model=JobOut)
async def get_job(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> JobOut:
    return await svc.get(id, user_id)


@router.patch("/{id}", response_model=JobOut)
async def patch_job(
    id: UUID, body: PatchJobInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> JobOut:
    return await svc.patch(id, user_id, body.model_dump(exclude_none=True))


@router.patch("/{id}/status", response_model=JobOut)
async def update_job_status(
    id: UUID, body: UpdateJobStatusInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> JobOut:
    # REQ-053: pass interview_time through to service for FR-003 validation
    return await svc.update_status(
        id, user_id, body.to, body.note, interview_time=body.interview_time
    )


@router.delete("/{id}", status_code=204, response_class=Response)
async def delete_job(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> Response:
    await svc.delete(id, user_id)
    return Response(status_code=204)


@router.get("/{id}/timeline", response_model=JobTimelineOut)
async def job_timeline(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: JobService = Depends(_get_service),
) -> dict:
    return await svc.timeline(id, user_id)


# --- REQ-053 FR-022: research report endpoints ---


@router.get("/{id}/research-reports")
async def list_job_research_reports(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_user_dep),
):
    """List all pre-interview research reports for a job, ordered by interview_time DESC."""
    from app.domain.interview_report import ResearchReportListOut
    from app.repositories.interview_report_repo import InterviewReportRepo
    repo = InterviewReportRepo(session)
    data = await repo.list_research_reports_for_job(id, user_id=user_id)
    return ResearchReportListOut(data=data).model_dump(mode="json")


@router.get("/{id}/research-reports/{report_id}")
async def get_job_research_report(
    id: UUID,
    report_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(db_session_user_dep),
):
    """Fetch a single research report. 404 if report doesn't belong to this job."""
    from fastapi import HTTPException
    from app.repositories.interview_report_repo import InterviewReportRepo
    repo = InterviewReportRepo(session)
    out = await repo.get_research_report(report_id, user_id=user_id)
    if out is None or out.job_id != id:
        raise HTTPException(status_code=404, detail="报告不存在")
    return out.model_dump(mode="json")


__all__ = ["router"]
