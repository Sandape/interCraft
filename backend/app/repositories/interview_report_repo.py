"""InterviewReportRepo — CRUD for interview_reports table (T032).

REQ-053: extends the table with `report_type`, `job_id`, `interview_time`,
`research_task_id`, `rating`, `delivery_status`, `delivered_at`,
`quality_check_passed` columns. This module adds research-aware CRUD methods
without changing the existing mock-interview paths.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interview_report import (
    DeliveryStatus,
    InterviewReportCreate,
    InterviewReportResponse,
    ResearchReportCreate,
    ResearchReportOut,
    ResearchReportSummary,
)


class InterviewReportRepo:
    """Repository for interview_reports table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: InterviewReportCreate) -> InterviewReportResponse:
        """Insert a new mock-interview report (existing path)."""
        report_id = uuid4()
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
        """Get report by session ID (existing mock-interview path)."""
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

    # --- REQ-053: pre_interview_research report methods ---

    async def create_research_report(
        self, data: ResearchReportCreate, *, quality_check_passed: bool = True
    ) -> ResearchReportOut:
        """Insert a pre_interview_research report. Returns full read schema."""
        report_id = uuid4()
        stmt = text(
            """INSERT INTO interview_reports
            (id, report_type, job_id, interview_time, research_task_id,
             summary_md, delivery_status, quality_check_passed, generated_at)
            VALUES (:id, 'pre_interview_research', :jid, :itime, :tid,
                    :sum, 'pending', :qcp, now())
            RETURNING id, report_type, job_id, interview_time, research_task_id,
                      summary_md, rating, delivery_status, delivered_at,
                      quality_check_passed, generated_at, created_at, updated_at"""
        )
        result = await self.session.execute(
            stmt,
            {
                "id": report_id,
                "jid": data.job_id,
                "itime": data.interview_time,
                "tid": data.research_task_id,
                "sum": data.summary_md,
                "qcp": quality_check_passed,
            },
        )
        await self.session.commit()
        row = result.fetchone()
        return _row_to_research_out(row)

    async def get_research_report(
        self, report_id: UUID, *, user_id: UUID | None = None
    ) -> ResearchReportOut | None:
        """Fetch a single research report by id. If user_id provided, enforce RLS."""
        user_filter = "AND j.user_id = :uid" if user_id is not None else ""
        stmt = text(
            f"""SELECT r.id, r.report_type, r.job_id, r.interview_time, r.research_task_id,
                      r.summary_md, r.rating, r.delivery_status, r.delivered_at,
                      r.quality_check_passed, r.generated_at, r.created_at, r.updated_at
            FROM interview_reports r
            JOIN jobs j ON j.id = r.job_id
            WHERE r.id = :rid
              AND r.report_type = 'pre_interview_research'
              {user_filter}"""
        )
        params: dict[str, Any] = {"rid": report_id}
        if user_id is not None:
            params["uid"] = user_id
        result = await self.session.execute(stmt, params)
        row = result.fetchone()
        return _row_to_research_out(row) if row else None

    async def list_research_reports_for_job(
        self, job_id: UUID, *, user_id: UUID | None = None
    ) -> list[ResearchReportSummary]:
        """List all research reports for a job, ordered by interview_time DESC."""
        user_filter = "AND j.user_id = :uid" if user_id is not None else ""
        stmt = text(
            f"""SELECT r.id, r.report_type, r.job_id, r.interview_time,
                      r.rating, r.delivery_status, r.generated_at
            FROM interview_reports r
            JOIN jobs j ON j.id = r.job_id
            WHERE r.job_id = :jid
              AND r.report_type = 'pre_interview_research'
              {user_filter}
            ORDER BY r.interview_time DESC"""
        )
        params: dict[str, Any] = {"jid": job_id}
        if user_id is not None:
            params["uid"] = user_id
        result = await self.session.execute(stmt, params)
        rows = result.fetchall()
        return [
            ResearchReportSummary(
                id=r[0],
                report_type=r[1],
                job_id=r[2],
                interview_time=r[3],
                rating=r[4],
                delivery_status=r[5],
                generated_at=r[6],
            )
            for r in rows
        ]

    async def update_rating(
        self, report_id: UUID, rating: int, *, user_id: UUID | None = None
    ) -> bool:
        """Update user rating (1-5). Returns True if row updated."""
        user_filter = (
            """AND EXISTS (
                  SELECT 1 FROM jobs j WHERE j.id = interview_reports.job_id AND j.user_id = :uid
              )"""
            if user_id is not None
            else ""
        )
        stmt = text(
            f"""UPDATE interview_reports
            SET rating = :rating, updated_at = now()
            WHERE id = :rid
              AND report_type = 'pre_interview_research'
              {user_filter}"""
        )
        params: dict[str, Any] = {"rating": rating, "rid": report_id}
        if user_id is not None:
            params["uid"] = user_id
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        return result.rowcount > 0

    async def update_delivery_status(
        self,
        report_id: UUID,
        *,
        delivery_status: DeliveryStatus,
        delivered_at: datetime | None = None,
    ) -> bool:
        """Update delivery status (and optionally delivered_at)."""
        stmt = text(
            """UPDATE interview_reports
            SET delivery_status = :status,
                delivered_at = COALESCE(:delivered_at, delivered_at),
                updated_at = now()
            WHERE id = :rid"""
        )
        result = await self.session.execute(
            stmt,
            {
                "status": delivery_status,
                "delivered_at": delivered_at,
                "rid": report_id,
            },
        )
        await self.session.commit()
        return result.rowcount > 0


def _row_to_research_out(row: Any) -> ResearchReportOut:
    """Map a DB row tuple to ResearchReportOut. Defensive against column order."""
    return ResearchReportOut(
        id=row[0],
        report_type=row[1],
        job_id=row[2],
        interview_time=row[3],
        research_task_id=row[4],
        summary_md=row[5] or "",
        rating=row[6],
        delivery_status=row[7],
        delivered_at=row[8],
        quality_check_passed=row[9],
        generated_at=row[10],
        created_at=row[11],
        updated_at=row[12],
    )


__all__ = ["InterviewReportRepo"]
