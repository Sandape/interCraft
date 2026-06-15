"""ResumeBlock repository — list / create / patch / reorder / soft-delete."""
from __future__ import annotations

from datetime import UTC
from uuid import UUID

from fractional_indexing import generate_key_between
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resumes.models import ResumeBlock
from app.repositories.base import BaseRepository


class ResumeBlockRepository(BaseRepository[ResumeBlock]):
    model = ResumeBlock

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_branch(
        self,
        branch_id: UUID,
        *,
        block_type: str | None = None,
        limit: int = 100,
    ) -> list[ResumeBlock]:
        stmt = select(ResumeBlock).where(
            ResumeBlock.branch_id == branch_id,
            ResumeBlock.deleted_at.is_(None),
        )
        if block_type is not None:
            stmt = stmt.where(ResumeBlock.type == block_type)
        stmt = stmt.order_by(ResumeBlock.order_index.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def max_order_index(self, branch_id: UUID) -> str | None:
        stmt = select(ResumeBlock.order_index).where(
            ResumeBlock.branch_id == branch_id,
            ResumeBlock.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        rows = [r for r in result.scalars().all() if r]
        return max(rows) if rows else None

    async def get(self, block_id: UUID) -> ResumeBlock | None:
        return await super().get(block_id)

    async def create_block(
        self,
        *,
        user_id: UUID,
        branch_id: UUID,
        block_type: str,
        title: str | None = None,
        content_md: str = "",
        meta: dict | None = None,
    ) -> ResumeBlock:
        last = await self.max_order_index(branch_id)
        order = generate_key_between(last, None)
        block = ResumeBlock(
            user_id=user_id,
            branch_id=branch_id,
            type=block_type,
            title=title,
            content_md=content_md,
            meta=meta,
            order_index=order,
        )
        return await self.create(block)

    async def patch(self, block_id: UUID, **patch) -> ResumeBlock | None:
        return await self.update(block_id, patch)

    async def reorder(
        self,
        *,
        block_id: UUID,
        prev_id: UUID | None,
        next_id: UUID | None,
    ) -> ResumeBlock | None:
        block = await self.get(block_id)
        if block is None:
            return None
        prev_order: str | None = None
        next_order: str | None = None
        if prev_id is not None:
            prev = await self.get(prev_id)
            if prev is None or prev.branch_id != block.branch_id:
                raise ValueError("prev_id not in same branch")
            prev_order = prev.order_index
        if next_id is not None:
            nxt = await self.get(next_id)
            if nxt is None or nxt.branch_id != block.branch_id:
                raise ValueError("next_id not in same branch")
            next_order = nxt.order_index
        new_index = generate_key_between(prev_order, next_order)
        block.order_index = new_index
        await self.session.flush()
        await self.session.refresh(block)
        return block

    async def touch_branch(self, branch_id: UUID) -> None:
        from datetime import datetime

        from app.modules.resumes.models import ResumeBranch

        stmt = select(ResumeBranch).where(ResumeBranch.id == branch_id)
        result = await self.session.execute(stmt)
        branch = result.scalar_one_or_none()
        if branch is not None:
            branch.last_edited_at = datetime.now(UTC)
            await self.session.flush()


__all__ = ["ResumeBlockRepository"]
