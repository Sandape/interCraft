"""InterviewReportRepo — CRUD for interview_reports table (T032)."""
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interview_report import InterviewReportCreate, InterviewReportResponse


class InterviewReportRepo:
    """Repository for interview_reports table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: InterviewReportCreate) -> InterviewReportResponse:
        """Insert a new interview report."""
        report_id = uuid4()
        # asyncpg needs JSONB columns to receive either a Python dict (which it
        # serializes) or a JSON string with an explicit `::jsonb` cast. The
        # previous version tried `::jsonb` on a `:name` bind param, which is a
        # parse error (`:pqs::jsonb` is two binds, neither defined).
        # Use bindparam(type_=JSONB) so SQLAlchemy serializes dicts properly.
        stmt = text(
            """INSERT INTO interview_reports
            (id, session_id, overall_score, per_question_score, dimension_scores,
             strengths, improvements, summary_md)
            VALUES (:id, :sid, :os, :pqs, :ds, :str, :imp, :sum)
            """
        ).bindparams(
            bindparam("pqs", type_=JSONB),
            bindparam("ds", type_=JSONB),
            bindparam("str", type_=JSONB),
            bindparam("imp", type_=JSONB),
        )
        await self.session.execute(
            stmt,
            {
                "id": report_id,
                "sid": data.session_id,
                "os": data.overall_score,
                "pqs": data.per_question_score,
                "ds": data.dimension_scores,
                "str": data.strengths,
                "imp": data.improvements,
                "sum": data.summary_md,
            },
        )
        await self.session.commit()
        return await self.get_by_session_id(data.session_id)

    async def get_by_session_id(self, session_id: UUID) -> InterviewReportResponse | None:
        """Get report by session ID."""
        result = await self.session.execute(
            text(
                """SELECT id, session_id, overall_score, per_question_score,
                dimension_scores, strengths, improvements, summary_md,
                generated_at, created_at
                FROM interview_reports WHERE session_id = :sid"""
            ),
            {"sid": session_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return InterviewReportResponse(
            id=row[0],
            session_id=row[1],
            overall_score=float(row[2]),
            per_question_score=row[3] if isinstance(row[3], list) else [],
            dimension_scores=row[4] if isinstance(row[4], dict) else {},
            strengths=row[5] if isinstance(row[5], list) else [],
            improvements=row[6] if isinstance(row[6], list) else [],
            summary_md=row[7] or "",
            generated_at=row[8],
            created_at=row[9],
        )


__all__ = ["InterviewReportRepo"]
