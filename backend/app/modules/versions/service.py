"""Versioning service: create manual versions, rollback, restore."""
from __future__ import annotations

import copy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import resume_versions_total
from app.modules.resumes.block_repository import ResumeBlockRepository
from app.modules.resumes.models import ResumeBlock, ResumeBranch
from app.modules.resumes.repository import ResumeRepository
from app.modules.versions.models import ResumeVersion
from app.modules.versions.repository import ResumeVersionRepository
from app.modules.versions.snapshot import build_snapshot, restore_version


class VersionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResumeVersionRepository(session)
        self.resumes = ResumeRepository(session)
        self.blocks = ResumeBlockRepository(session)

    async def list_versions(
        self, branch_id: UUID, user_id: UUID, *, limit: int = 50
    ) -> list[ResumeVersion]:
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return []
        return await self.repo.list_for_branch(branch_id, limit=limit)

    async def get_version(
        self, branch_id: UUID, version_no: int, user_id: UUID
    ) -> ResumeVersion | None:
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        return await self.repo.get_by_no(branch_id, version_no)

    async def create_initial_version(
        self,
        *,
        branch_id: UUID,
        user_id: UUID,
        snapshot: dict,
    ) -> ResumeVersion:
        version_no = await self.repo.next_version_no(branch_id)
        v = await self.repo.create_full_snapshot(
            user_id=user_id,
            branch_id=branch_id,
            version_no=version_no,
            snapshot=snapshot,
            label="初始化",
            trigger="manual",
            author_type="user",
            actor_id=user_id,
        )
        resume_versions_total.labels(trigger="manual").inc()
        return v

    async def create_manual_version(
        self,
        *,
        branch_id: UUID,
        user_id: UUID,
        label: str | None = None,
    ) -> ResumeVersion | None:
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        blocks = await self.blocks.list_for_branch(branch_id)
        snapshot = build_snapshot(branch, blocks)
        version_no = await self.repo.next_version_no(branch_id)
        v = await self.repo.create_full_snapshot(
            user_id=user_id,
            branch_id=branch_id,
            version_no=version_no,
            snapshot=snapshot,
            label=label,
            trigger="manual",
            author_type="user",
            actor_id=user_id,
        )
        resume_versions_total.labels(trigger="manual").inc()
        return v

    async def get_snapshot(
        self, branch_id: UUID, version_no: int, user_id: UUID
    ) -> dict | None:
        v = await self.get_version(branch_id, version_no, user_id)
        if v is None:
            return None
        return await restore_version(self.session, v.id)

    async def rollback_to_version(
        self,
        *,
        branch_id: UUID,
        version_no: int,
        user_id: UUID,
        new_name: str | None = None,
    ) -> ResumeBranch | None:
        target = await self.get_version(branch_id, version_no, user_id)
        if target is None:
            return None
        snapshot = await restore_version(self.session, target.id)
        original = await self.resumes.get(branch_id, user_id=user_id)
        if original is None:
            return None
        if new_name is None:
            new_name = f"回滚自 {original.name} @ v{version_no}"
        new_branch = ResumeBranch(
            user_id=user_id,
            parent_id=original.id,
            name=new_name,
            company=original.company,
            position=original.position,
            status=original.status,
        )
        self.session.add(new_branch)
        await self.session.flush()
        await self.session.refresh(new_branch)

        for sb in snapshot.get("blocks", []):
            self.session.add(
                ResumeBlock(
                    user_id=user_id,
                    branch_id=new_branch.id,
                    type=sb.get("type", "custom"),
                    title=sb.get("title"),
                    content_md=sb.get("content_md", ""),
                    meta=copy.deepcopy(sb.get("meta")) if sb.get("meta") else None,
                    order_index=sb.get("order_index", "a0"),
                )
            )
        await self.session.flush()

        # Initial version on the new branch
        new_blocks = await self.blocks.list_for_branch(new_branch.id)
        snap = build_snapshot(new_branch, new_blocks)
        await self.create_initial_version(
            branch_id=new_branch.id,
            user_id=user_id,
            snapshot=snap,
        )
        # Patch the label slightly
        from sqlalchemy import update

        stmt = (
            update(ResumeVersion)
            .where(
                ResumeVersion.branch_id == new_branch.id,
                ResumeVersion.label == "初始化",
            )
            .values(label=f"回滚自 v{version_no}")
        )
        await self.session.execute(stmt)
        return new_branch


__all__ = ["VersionService"]
