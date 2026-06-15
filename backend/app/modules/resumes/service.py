"""Resume service — orchestrates branch + block operations."""
from __future__ import annotations

import copy
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.modules.resumes.block_repository import ResumeBlockRepository
from app.modules.resumes.models import ResumeBlock, ResumeBranch
from app.modules.resumes.repository import ResumeRepository
from app.modules.versions.service import VersionService
from app.modules.versions.snapshot import build_snapshot


class ResumeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResumeRepository(session)
        self.blocks = ResumeBlockRepository(session)
        self.versions = VersionService(session)

    async def list_branches(self, user_id: UUID, **filters) -> list[ResumeBranch]:
        return await self.repo.list_for_user(user_id, **filters)

    async def get_branch(self, branch_id: UUID, user_id: UUID) -> ResumeBranch | None:
        return await self.repo.get(branch_id, user_id=user_id)

    async def create_branch(
        self,
        *,
        user_id: UUID,
        name: str,
        company: str | None,
        position: str | None,
        parent_id: UUID | None,
        is_main: bool,
    ) -> ResumeBranch:
        # Validate parent (RLS will also gate, but be explicit)
        if parent_id is not None:
            parent = await self.repo.get(parent_id, user_id=user_id)
            if parent is None:
                raise NotFoundError("resume.not_found", "Parent branch not found")

        if is_main:
            await self.repo.ensure_single_main(user_id)

        branch = ResumeBranch(
            user_id=user_id,
            parent_id=parent_id,
            name=name,
            company=company,
            position=position,
            is_main=is_main,
        )
        branch = await self.repo.create(branch)

        cloned = 0
        if parent_id is not None:
            parent_blocks = await self.blocks.list_for_branch(parent_id)
            for pb in parent_blocks:
                new_block = ResumeBlock(
                    user_id=user_id,
                    branch_id=branch.id,
                    type=pb.type,
                    title=pb.title,
                    content_md=pb.content_md,
                    content_html=pb.content_html,
                    meta=copy.deepcopy(pb.meta) if pb.meta else None,
                    order_index=pb.order_index,
                    collapsed=pb.collapsed,
                )
                self.session.add(new_block)
                cloned += 1
            await self.session.flush()

        # Initial full-snapshot version (per contracts/resumes.md §2).
        snapshot = build_snapshot(branch, await self.blocks.list_for_branch(branch.id))
        await self.versions.create_initial_version(branch_id=branch.id, user_id=user_id, snapshot=snapshot)
        return branch

    async def patch_branch(
        self, branch_id: UUID, user_id: UUID, **patch
    ) -> ResumeBranch | None:
        branch = await self.repo.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        for k, v in patch.items():
            if hasattr(branch, k):
                setattr(branch, k, v)
        branch.last_edited_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(branch)
        return branch

    async def delete_branch(self, branch_id: UUID, user_id: UUID) -> bool:
        branch = await self.repo.get(branch_id, user_id=user_id)
        if branch is None:
            return False
        if branch.is_main:
            raise AppError(
                "resume.cannot_delete_main",
                "Cannot delete the main resume branch",
                http_status=422,
            )
        return await self.repo.soft_delete(branch_id, user_id=user_id)

    async def refresh_from_parent(
        self, branch_id: UUID, user_id: UUID
    ) -> tuple[ResumeBranch | None, int]:
        branch = await self.repo.get(branch_id, user_id=user_id)
        if branch is None or branch.parent_id is None:
            return branch, 0
        parent_id = branch.parent_id
        # Phase 1 simplified: drop all current blocks and re-clone from parent.
        current = await self.blocks.list_for_branch(branch_id)
        for cb in current:
            cb.deleted_at = datetime.now(UTC)
        parent_blocks = await self.blocks.list_for_branch(parent_id)
        cloned = 0
        for pb in parent_blocks:
            self.session.add(
                ResumeBlock(
                    user_id=user_id,
                    branch_id=branch_id,
                    type=pb.type,
                    title=pb.title,
                    content_md=pb.content_md,
                    content_html=pb.content_html,
                    meta=copy.deepcopy(pb.meta) if pb.meta else None,
                    order_index=pb.order_index,
                    collapsed=False,  # reset collapse on refresh
                )
            )
            cloned += 1
        branch.last_edited_at = datetime.now(UTC)
        await self.session.flush()
        return branch, cloned

    # ---- Blocks ----
    async def list_blocks(
        self, branch_id: UUID, user_id: UUID, *, block_type: str | None = None
    ) -> list[ResumeBlock]:
        branch = await self.repo.get(branch_id, user_id=user_id)
        if branch is None:
            return []
        return await self.blocks.list_for_branch(branch_id, block_type=block_type)

    async def create_block(
        self,
        branch_id: UUID,
        user_id: UUID,
        *,
        block_type: str,
        title: str | None,
        content_md: str,
        meta: dict | None,
    ) -> ResumeBlock | None:
        branch = await self.repo.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        block = await self.blocks.create_block(
            user_id=user_id,
            branch_id=branch_id,
            block_type=block_type,
            title=title,
            content_md=content_md,
            meta=meta,
        )
        branch.last_edited_at = datetime.now(UTC)
        await self.session.flush()
        return block

    async def patch_block(self, block_id: UUID, user_id: UUID, **patch) -> ResumeBlock | None:
        block = await self.blocks.get(block_id)
        if block is None or block.user_id != user_id:
            return None
        updated = await self.blocks.patch(block_id, **patch)
        if updated is not None:
            branch = await self.repo.get(updated.branch_id, user_id=user_id)
            if branch is not None:
                branch.last_edited_at = datetime.now(UTC)
                await self.session.flush()
        return updated

    async def reorder_block(
        self,
        *,
        block_id: UUID,
        user_id: UUID,
        prev_id: UUID | None,
        next_id: UUID | None,
    ) -> ResumeBlock | None:
        block = await self.blocks.get(block_id)
        if block is None or block.user_id != user_id:
            return None
        try:
            moved = await self.blocks.reorder(
                block_id=block_id, prev_id=prev_id, next_id=next_id
            )
        except ValueError as e:
            raise ValidationError("validation.inconsistent_reorder", str(e)) from e
        if moved is not None:
            await self.blocks.touch_branch(moved.branch_id)
        return moved

    async def delete_block(self, block_id: UUID, user_id: UUID) -> bool:
        block = await self.blocks.get(block_id)
        if block is None or block.user_id != user_id:
            return False
        ok = await self.blocks.soft_delete(block_id)
        if ok:
            await self.blocks.touch_branch(block.branch_id)
        return ok


__all__ = ["ResumeService"]
