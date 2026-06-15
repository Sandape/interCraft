"""M07 — versions API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.exceptions import NotFoundError
from app.modules.versions.schemas import (
    CreateVersionInput,
    CreateVersionResponse,
    ResumeVersionDetail,
    ResumeVersionSummary,
    RollbackInput,
    RollbackResponse,
    Snapshot,
    VersionDetailResponse,
    VersionsListResponse,
)
from app.modules.versions.service import VersionService

router = APIRouter()


@router.get(
    "/resume-branches/{branch_id}/versions",
    response_model=VersionsListResponse,
)
async def list_versions(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = VersionService(db)
    rows = await svc.list_versions(branch_id, user_id)
    return VersionsListResponse(
        data=[ResumeVersionSummary.model_validate(r) for r in rows]
    )


@router.post(
    "/resume-branches/{branch_id}/versions",
    response_model=CreateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    branch_id: UUID,
    payload: CreateVersionInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = VersionService(db)
    v = await svc.create_manual_version(
        branch_id=branch_id, user_id=user_id, label=payload.label
    )
    if v is None:
        raise NotFoundError("resume.not_found", "Branch not found")
    return CreateVersionResponse(version=ResumeVersionSummary.model_validate(v))


@router.get(
    "/resume-branches/{branch_id}/versions/{version_no}",
    response_model=VersionDetailResponse,
)
async def get_version(
    branch_id: UUID,
    version_no: int,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = VersionService(db)
    v = await svc.get_version(branch_id, version_no, user_id)
    if v is None:
        raise NotFoundError("resume.version_not_found", "Version not found")
    snap = await svc.get_snapshot(branch_id, version_no, user_id)
    if snap is None:
        raise NotFoundError("resume.version_not_found", "Version not found")
    detail = ResumeVersionDetail(
        id=str(v.id),
        branch_id=str(v.branch_id),
        version_no=v.version_no,
        label=v.label,
        is_full_snapshot=v.is_full_snapshot,
        trigger=v.trigger,
        author_type=v.author_type,
        actor_id=str(v.actor_id) if v.actor_id else None,
        created_at=v.created_at,
        snapshot=Snapshot.model_validate(snap),
    )
    return VersionDetailResponse(version=detail)


@router.post(
    "/resume-branches/{branch_id}/versions/{version_no}/rollback",
    response_model=RollbackResponse,
)
async def rollback(
    branch_id: UUID,
    version_no: int,
    payload: RollbackInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = VersionService(db)
    new_branch = await svc.rollback_to_version(
        branch_id=branch_id,
        version_no=version_no,
        user_id=user_id,
        new_name=payload.name,
    )
    if new_branch is None:
        raise NotFoundError("resume.version_not_found", "Version or branch not found")
    return RollbackResponse(new_branch_id=str(new_branch.id))
