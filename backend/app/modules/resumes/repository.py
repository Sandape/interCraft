"""ResumeBranch repository."""
from __future__ import annotations

from datetime import UTC
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resumes.models import ResumeBlock, ResumeBranch
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[ResumeBranch]):
    model = ResumeBranch

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        is_main: bool | None = None,
        is_pinned: bool | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ResumeBranch]:
        # 022: list_branches does not serialize branch.versions / branch.blocks
        # (the response schema ResumeBranchOut only carries scalar counts,
        # populated separately by get_counts_batch). Eager-loading those
        # relationships would issue 2 unused SQL roundtrips; the counts come
        # from get_counts_batch (2 GROUP BY queries) instead. Total queries:
        # 1 (this list) + 2 (batch COUNT) = 3, constant regardless of branch
        # count (was 1 + 2N before).
        stmt = (
            select(ResumeBranch)
            .where(
                ResumeBranch.user_id == user_id,
                ResumeBranch.deleted_at.is_(None),
            )
        )
        if is_main is not None:
            stmt = stmt.where(ResumeBranch.is_main == is_main)
        if is_pinned is not None:
            stmt = stmt.where(ResumeBranch.is_pinned == is_pinned)
        if status is not None:
            stmt = stmt.where(ResumeBranch.status == status)
        stmt = stmt.order_by(
            ResumeBranch.is_pinned.desc(),
            ResumeBranch.is_main.desc(),
            ResumeBranch.last_edited_at.desc(),
        ).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_counts_batch(
        self,
        branch_ids: list[UUID],
    ) -> dict[UUID, tuple[int, int]]:
        """Return {branch_id: (version_count, block_count)} in 2 SQL roundtrips.

        022: used by list_branches to avoid N+1 per-branch COUNT queries.
        """
        from app.modules.versions.models import ResumeVersion

        if not branch_ids:
            return {}

        v_stmt = (
            select(ResumeVersion.branch_id, func.count())
            .where(ResumeVersion.branch_id.in_(branch_ids))
            .group_by(ResumeVersion.branch_id)
        )
        b_stmt = (
            select(ResumeBlock.branch_id, func.count())
            .where(
                ResumeBlock.branch_id.in_(branch_ids),
                ResumeBlock.deleted_at.is_(None),
            )
            .group_by(ResumeBlock.branch_id)
        )
        v_result = await self.session.execute(v_stmt)
        b_result = await self.session.execute(b_stmt)
        v_map = {row[0]: int(row[1] or 0) for row in v_result.all()}
        b_map = {row[0]: int(row[1] or 0) for row in b_result.all()}
        return {bid: (v_map.get(bid, 0), b_map.get(bid, 0)) for bid in branch_ids}

    async def get(self, branch_id: UUID, *, user_id: UUID | None = None) -> ResumeBranch | None:
        stmt = select(ResumeBranch).where(
            ResumeBranch.id == branch_id,
            ResumeBranch.deleted_at.is_(None),
        )
        if user_id is not None:
            stmt = stmt.where(ResumeBranch.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def ensure_single_main(self, user_id: UUID, except_id: UUID | None = None) -> None:
        """Clear all is_main flags for this user, except the given branch id."""
        stmt = select(ResumeBranch).where(
            ResumeBranch.user_id == user_id,
            ResumeBranch.is_main == True,  # noqa: E712
            ResumeBranch.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        for row in result.scalars().all():
            if except_id is None or row.id != except_id:
                row.is_main = False
        await self.session.flush()

    async def soft_delete(self, branch_id: UUID, *, user_id: UUID | None = None) -> bool:
        branch = await self.get(branch_id, user_id=user_id)
        if branch is None:
            return False
        from datetime import datetime

        branch.deleted_at = datetime.now(UTC)
        # cascade blocks
        blocks_stmt = select(ResumeBlock).where(
            ResumeBlock.branch_id == branch_id,
            ResumeBlock.deleted_at.is_(None),
        )
        result = await self.session.execute(blocks_stmt)
        for b in result.scalars().all():
            b.deleted_at = datetime.now(UTC)
        # cascade versions — ResumeVersion is immutable (no deleted_at per spec T115),
        # so hard-delete them when the parent branch is gone.
        from app.modules.versions.models import ResumeVersion

        ver_stmt = select(ResumeVersion).where(ResumeVersion.branch_id == branch_id)
        ver_result = await self.session.execute(ver_stmt)
        for v in ver_result.scalars().all():
            await self.session.delete(v)
        await self.session.flush()
        return True

    async def get_version_count(self, branch_id: UUID) -> int:
        from app.modules.versions.models import ResumeVersion

        stmt = select(func.count()).select_from(ResumeVersion).where(
            ResumeVersion.branch_id == branch_id,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def get_block_count(self, branch_id: UUID) -> int:
        stmt = select(func.count()).select_from(ResumeBlock).where(
            ResumeBlock.branch_id == branch_id,
            ResumeBlock.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)


__all__ = ["ResumeRepository"]
