"""M06 — Resumes API (branches + blocks)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.resumes.schemas import (
    CreateBlockInput,
    CreateBlockResponse,
    CreateBranchInput,
    CreateBranchResponse,
    PatchBlockInput,
    PatchBranchInput,
    RefreshFromParentResponse,
    ReorderBlocksInput,
    ResumeBlockListResponse,
    ResumeBlockOut,
    ResumeBranchListResponse,
    ResumeBranchOut,
)
from app.modules.resumes.service import ResumeService

router = APIRouter()


async def _branch_out(branch, block_count: int, version_count: int) -> ResumeBranchOut:
    return ResumeBranchOut(
        id=str(branch.id),
        parent_id=str(branch.parent_id) if branch.parent_id else None,
        name=branch.name,
        company=branch.company,
        position=branch.position,
        status=branch.status,
        match_score=float(branch.match_score) if branch.match_score is not None else None,
        is_main=branch.is_main,
        is_pinned=branch.is_pinned,
        style_preference=branch.style_preference,
        last_edited_at=branch.last_edited_at,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
        version_count=version_count,
        block_count=block_count,
    )


@router.get("/resume-branches", response_model=ResumeBranchListResponse)
async def list_branches(
    is_main: bool | None = None,
    is_pinned: bool | None = None,
    status_filter: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    branches = await svc.list_branches(
        user_id,
        is_main=is_main,
        is_pinned=is_pinned,
        status=status_filter,
    )
    out: list[ResumeBranchOut] = []
    for b in branches:
        bc = await svc.repo.get_block_count(b.id)
        vc = await svc.repo.get_version_count(b.id)
        out.append(await _branch_out(b, bc, vc))
    return ResumeBranchListResponse(data=out)


@router.post(
    "/resume-branches",
    response_model=CreateBranchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_branch(
    payload: CreateBranchInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    branch = await svc.create_branch(
        user_id=user_id,
        name=payload.name,
        company=payload.company,
        position=payload.position,
        parent_id=UUID(payload.parent_id) if payload.parent_id else None,
        is_main=payload.is_main,
    )
    bc = await svc.repo.get_block_count(branch.id)
    vc = await svc.repo.get_version_count(branch.id)
    return CreateBranchResponse(branch=await _branch_out(branch, bc, vc))


@router.get("/resume-branches/{branch_id}", response_model=CreateBranchResponse)
async def get_branch(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    branch = await svc.get_branch(branch_id, user_id)
    if branch is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("resume.not_found", "Branch not found")
    bc = await svc.repo.get_block_count(branch.id)
    vc = await svc.repo.get_version_count(branch.id)
    return CreateBranchResponse(branch=await _branch_out(branch, bc, vc))


@router.patch("/resume-branches/{branch_id}", response_model=CreateBranchResponse)
async def patch_branch(
    branch_id: UUID,
    payload: PatchBranchInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    branch = await svc.patch_branch(branch_id, user_id, **payload.model_dump(exclude_unset=True))
    if branch is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("resume.not_found", "Branch not found")
    bc = await svc.repo.get_block_count(branch.id)
    vc = await svc.repo.get_version_count(branch.id)
    return CreateBranchResponse(branch=await _branch_out(branch, bc, vc))


@router.delete("/resume-branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    await svc.delete_branch(branch_id, user_id)
    return None


@router.post(
    "/resume-branches/{branch_id}/refresh-from-parent",
    response_model=RefreshFromParentResponse,
)
async def refresh_from_parent(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    branch, cloned = await svc.refresh_from_parent(branch_id, user_id)
    if branch is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("resume.not_found", "Branch not found")
    bc = await svc.repo.get_block_count(branch.id)
    vc = await svc.repo.get_version_count(branch.id)
    return RefreshFromParentResponse(
        branch=await _branch_out(branch, bc, vc), cloned_blocks=cloned
    )


# ---- Blocks ----
@router.get(
    "/resume-branches/{branch_id}/blocks",
    response_model=ResumeBlockListResponse,
)
async def list_blocks(
    branch_id: UUID,
    type: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    rows = await svc.list_blocks(branch_id, user_id, block_type=type)
    return ResumeBlockListResponse(
        data=[ResumeBlockOut.model_validate(r) for r in rows]
    )


@router.post(
    "/resume-branches/{branch_id}/blocks",
    response_model=CreateBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_block(
    branch_id: UUID,
    payload: CreateBlockInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    block = await svc.create_block(
        branch_id,
        user_id,
        block_type=payload.type,
        title=payload.title,
        content_md=payload.content_md,
        meta=payload.meta,
    )
    if block is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("resume.not_found", "Branch not found")
    return CreateBlockResponse(block=ResumeBlockOut.model_validate(block))


@router.get("/resume-blocks/{block_id}", response_model=CreateBlockResponse)
async def get_block(
    block_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    block = await svc.blocks.get(block_id)
    if block is None or block.user_id != user_id:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("block.not_found", "Block not found")
    return CreateBlockResponse(block=ResumeBlockOut.model_validate(block))


@router.patch("/resume-blocks/{block_id}", response_model=CreateBlockResponse)
async def patch_block(
    block_id: UUID,
    payload: PatchBlockInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    block = await svc.patch_block(block_id, user_id, **payload.model_dump(exclude_unset=True))
    if block is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("block.not_found", "Block not found")
    return CreateBlockResponse(block=ResumeBlockOut.model_validate(block))


@router.patch("/resume-blocks/{block_id}/reorder", response_model=CreateBlockResponse)
async def reorder_block(
    block_id: UUID,
    payload: ReorderBlocksInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    block = await svc.reorder_block(
        block_id=block_id,
        user_id=user_id,
        prev_id=UUID(payload.prev_id) if payload.prev_id else None,
        next_id=UUID(payload.next_id) if payload.next_id else None,
    )
    if block is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("block.not_found", "Block not found")
    return CreateBlockResponse(block=ResumeBlockOut.model_validate(block))


@router.delete("/resume-blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    block_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ResumeService(db)
    await svc.delete_block(block_id, user_id)
    return None
