"""Tenant-scoped repositories for immutable analyses and AI actions."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resume_intelligence.models import (
    ResumeAIChangeSet,
    ResumeAIFeedback,
    ResumeAISuggestion,
    ResumeFitAnalysis,
)


class ResumeIntelligenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_analysis(self, row: ResumeFitAnalysis) -> ResumeFitAnalysis:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_analysis(
        self, analysis_id: UUID, *, user_id: UUID
    ) -> ResumeFitAnalysis | None:
        result = await self.session.execute(
            select(ResumeFitAnalysis).where(
                ResumeFitAnalysis.id == analysis_id,
                ResumeFitAnalysis.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_analyses(
        self, resume_id: UUID, *, user_id: UUID, mode: str | None = None
    ) -> list[ResumeFitAnalysis]:
        stmt = select(ResumeFitAnalysis).where(
            ResumeFitAnalysis.resume_id == resume_id,
            ResumeFitAnalysis.user_id == user_id,
        )
        if mode:
            stmt = stmt.where(ResumeFitAnalysis.mode == mode)
        result = await self.session.execute(stmt.order_by(ResumeFitAnalysis.created_at.desc()))
        return list(result.scalars().all())

    async def add_suggestions(
        self, rows: Iterable[ResumeAISuggestion]
    ) -> list[ResumeAISuggestion]:
        values = list(rows)
        self.session.add_all(values)
        await self.session.flush()
        return values

    async def list_suggestions(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        analysis_id: UUID,
    ) -> list[ResumeAISuggestion]:
        result = await self.session.execute(
            select(ResumeAISuggestion)
            .where(
                ResumeAISuggestion.user_id == user_id,
                ResumeAISuggestion.resume_id == resume_id,
                ResumeAISuggestion.analysis_id == analysis_id,
            )
            .order_by(ResumeAISuggestion.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_suggestion(
        self, suggestion_id: UUID, *, user_id: UUID
    ) -> ResumeAISuggestion | None:
        result = await self.session.execute(
            select(ResumeAISuggestion).where(
                ResumeAISuggestion.id == suggestion_id,
                ResumeAISuggestion.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_change_set(
        self, change_set_id: UUID, *, user_id: UUID
    ) -> ResumeAIChangeSet | None:
        result = await self.session.execute(
            select(ResumeAIChangeSet).where(
                ResumeAIChangeSet.id == change_set_id,
                ResumeAIChangeSet.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_suggestion_status(
        self,
        suggestion_id: UUID,
        *,
        user_id: UUID,
        status: str,
        reason: str | None = None,
    ) -> ResumeAISuggestion | None:
        row = await self.get_suggestion(suggestion_id, user_id=user_id)
        if row is None:
            return None
        row.status = status
        row.status_reason = reason
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        return row

    async def add_feedback(self, row: ResumeAIFeedback) -> ResumeAIFeedback:
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_feedback(
        self, *, user_id: UUID, analysis_id: UUID
    ) -> list[ResumeAIFeedback]:
        result = await self.session.execute(
            select(ResumeAIFeedback)
            .where(
                ResumeAIFeedback.user_id == user_id,
                ResumeAIFeedback.analysis_id == analysis_id,
            )
            .order_by(ResumeAIFeedback.created_at.asc())
        )
        return list(result.scalars().all())

    async def cancel_analysis(
        self, analysis_id: UUID, *, user_id: UUID
    ) -> ResumeFitAnalysis | None:
        row = await self.get_analysis(analysis_id, user_id=user_id)
        if row is None:
            return None
        if row.status in {"complete", "partial", "failed", "cancelled"}:
            return row
        row.status = "cancelled"
        row.error_code = "RUN_CANCELLED"
        row.finished_at = datetime.now(UTC)
        await self.session.flush()
        return row
