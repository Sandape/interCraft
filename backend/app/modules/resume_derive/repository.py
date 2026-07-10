"""Repository for resume_derive_runs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.resume_derive.models import ResumeDeriveRun


class ResumeDeriveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
        root_resume_id: UUID,
        root_version: int,
        target_page_count: int,
        template_id: str,
    ) -> ResumeDeriveRun:
        row = ResumeDeriveRun(
            id=new_uuid_v7(),
            user_id=user_id,
            job_id=job_id,
            root_resume_id=root_resume_id,
            root_version=root_version,
            target_page_count=target_page_count,
            template_id=template_id,
            status="pending",
            phase="parse_jd",
            calibrate_round=0,
            progress_pct=0,
            artifacts={},
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, run_id: UUID, *, user_id: UUID) -> ResumeDeriveRun | None:
        stmt = select(ResumeDeriveRun).where(
            ResumeDeriveRun.id == run_id,
            ResumeDeriveRun.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_fields(
        self,
        run_id: UUID,
        *,
        user_id: UUID,
        **fields: Any,
    ) -> ResumeDeriveRun | None:
        fields["updated_at"] = datetime.now(timezone.utc)
        stmt = (
            update(ResumeDeriveRun)
            .where(ResumeDeriveRun.id == run_id, ResumeDeriveRun.user_id == user_id)
            .values(**fields)
            .returning(ResumeDeriveRun)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        await self._session.flush()
        return row
