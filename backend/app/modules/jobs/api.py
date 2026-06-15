"""Jobs API (M10) — 7 endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, db_session_user_dep
from app.core.db import get_db_session
from app.modules.jobs.schemas import (
    CreateJobInput, JobListOut, JobOut, JobStatsOut, JobTimelineOut,
    PatchJobInput, UpdateJobStatusInput,
)
from app.modules.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> JobService:
    return JobService(session)


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
    return await svc.update_status(id, user_id, body.to, body.note)


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


__all__ = ["router"]
