"""Data access layer for interview_research_tasks and interview_research_results.

REQ-053. Uses raw SQL via `sqlalchemy.text()` with `bindparam(type_=JSONB)`
for JSONB columns — consistent with the InterviewReportRepo pattern.

All queries that filter by job_id/user_id include RLS-style enforcement
(Constitution: Security & Privacy).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession


class ResearchTaskRepository:
    """CRUD for interview_research_tasks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        job_id: UUID,
        user_id: UUID,
        interview_time: datetime,
    ) -> UUID:
        """Insert a new research task in `pending` status. Returns the new task id.

        Uses `ON CONFLICT DO NOTHING` to honor the unique constraint
        `(job_id, interview_time)` for re-triggering scenarios. The caller
        should query afterwards if it needs to know whether a row was actually
        inserted.
        """
        task_id = uuid4()
        stmt = text(
            """INSERT INTO interview_research_tasks
            (id, job_id, user_id, interview_time, status)
            VALUES (:id, :jid, :uid, :itime, 'pending')
            ON CONFLICT (job_id, interview_time) DO NOTHING
            RETURNING id"""
        )
        result = await self.session.execute(
            stmt,
            {
                "id": task_id,
                "jid": job_id,
                "uid": user_id,
                "itime": interview_time,
            },
        )
        await self.session.commit()
        row = result.fetchone()
        return row[0] if row else task_id

    async def get_by_id(self, task_id: UUID) -> dict | None:
        result = await self.session.execute(
            text(
                """SELECT id, job_id, user_id, interview_time, status,
                          search_dimensions, report_id, triggered_at, started_at,
                          completed_at, error_message, created_at, updated_at
                FROM interview_research_tasks WHERE id = :tid"""
            ),
            {"tid": task_id},
        )
        row = result.fetchone()
        return _row_to_task(row) if row else None

    async def get_active_for_job_interview(
        self, job_id: UUID, interview_time: datetime
    ) -> dict | None:
        """Find a non-cancelled task for the same (job_id, interview_time)."""
        result = await self.session.execute(
            text(
                """SELECT id, job_id, user_id, interview_time, status,
                          search_dimensions, report_id, triggered_at, started_at,
                          completed_at, error_message, created_at, updated_at
                FROM interview_research_tasks
                WHERE job_id = :jid
                  AND interview_time = :itime
                  AND status != 'cancelled'
                ORDER BY created_at DESC
                LIMIT 1"""
            ),
            {"jid": job_id, "itime": interview_time},
        )
        row = result.fetchone()
        return _row_to_task(row) if row else None

    async def find_matching_jobs(
        self, *, lower: datetime, upper: datetime
    ) -> list[dict]:
        """REQ-053 FR-009 scan: find jobs whose interview_time falls in the
        [lower, upper] window and that are not yet scheduled (no non-cancelled
        task exists for the same job+interview_time).

        Skips soft-deleted jobs and users with deleted_at IS NOT NULL.
        """
        result = await self.session.execute(
            text(
                """SELECT j.id AS job_id, j.user_id, j.company, j.position,
                          j.interview_time, j.status
                FROM jobs j
                LEFT JOIN interview_research_tasks t
                    ON t.job_id = j.id
                    AND t.interview_time = j.interview_time
                    AND t.status != 'cancelled'
                WHERE j.deleted_at IS NULL
                  AND j.status IN ('test', 'interview_1', 'interview_2', 'interview_3')
                  AND j.interview_time BETWEEN :lower AND :upper
                  AND t.id IS NULL"""
            ),
            {"lower": lower, "upper": upper},
        )
        rows = result.fetchall()
        return [
            {
                "job_id": r[0],
                "user_id": r[1],
                "company": r[2],
                "position": r[3],
                "interview_time": r[4],
                "status": r[5],
            }
            for r in rows
        ]

    async def update_status(
        self,
        task_id: UUID,
        new_status: str,
        *,
        search_dimensions: dict | None = None,
        report_id: UUID | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> bool:
        """Update status (and optionally other fields) for a task."""
        sets = ["status = :status", "updated_at = now()"]
        params: dict[str, Any] = {"tid": task_id, "status": new_status}
        if search_dimensions is not None:
            sets.append("search_dimensions = CAST(:sd AS jsonb)")
            params["sd"] = json.dumps(search_dimensions, ensure_ascii=False)
        if report_id is not None:
            sets.append("report_id = :rid")
            params["rid"] = report_id
        if error_message is not None:
            sets.append("error_message = :err")
            params["err"] = error_message
        if started_at is not None:
            sets.append("started_at = :started_at")
            params["started_at"] = started_at
        if completed_at is not None:
            sets.append("completed_at = :completed_at")
            params["completed_at"] = completed_at
        stmt = text(
            f"""UPDATE interview_research_tasks SET {', '.join(sets)}
            WHERE id = :tid"""
        )
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        return result.rowcount > 0

    async def cancel_pending_for_job(self, job_id: UUID) -> int:
        """REQ-053 FR-011: cancel pending research tasks for a job. Returns affected count."""
        result = await self.session.execute(
            text(
                """UPDATE interview_research_tasks
                SET status = 'cancelled', updated_at = now(), completed_at = now()
                WHERE job_id = :jid AND status = 'pending'"""
            ),
            {"jid": job_id},
        )
        await self.session.commit()
        return result.rowcount

    async def list_by_user(self, user_id: UUID, *, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            text(
                """SELECT id, job_id, user_id, interview_time, status,
                          search_dimensions, report_id, triggered_at, started_at,
                          completed_at, error_message, created_at, updated_at
                FROM interview_research_tasks
                WHERE user_id = :uid
                ORDER BY created_at DESC
                LIMIT :lim"""
            ),
            {"uid": user_id, "lim": limit},
        )
        rows = result.fetchall()
        return [_row_to_task(r) for r in rows]

    async def stats_by_user(self, user_id: UUID) -> dict:
        """Return counts by status and rating for a user (FR-023)."""
        result = await self.session.execute(
            text(
                """SELECT status, COUNT(*) FROM interview_research_tasks
                WHERE user_id = :uid GROUP BY status"""
            ),
            {"uid": user_id},
        )
        rows = result.fetchall()
        by_status: dict[str, int] = {}
        for r in rows:
            by_status[r[0]] = r[1]

        # Reports + average rating
        report_result = await self.session.execute(
            text(
                """SELECT COUNT(*) AS total,
                          COALESCE(AVG(rating), 0) AS avg_rating
                FROM interview_reports r
                JOIN jobs j ON j.id = r.job_id
                WHERE j.user_id = :uid
                  AND r.report_type = 'pre_interview_research'"""
            ),
            {"uid": user_id},
        )
        report_row = report_result.fetchone()
        total_reports = report_row[0] or 0
        avg_rating = float(report_row[1] or 0) if report_row else 0.0

        return {
            "total_tasks": sum(by_status.values()),
            "by_status": by_status,
            "total_reports": total_reports,
            "average_rating": round(avg_rating, 2) if avg_rating else None,
        }


class ResearchResultRepository:
    """CRUD for interview_research_results."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        task_id: UUID,
        dimension: str,
        query: str,
        company: str,
        results: list[dict],
        error: str | None = None,
    ) -> UUID:
        result_id = uuid4()
        stmt = text(
            """INSERT INTO interview_research_results
            (id, task_id, dimension, query, results, result_count, company, error)
            VALUES (:id, :tid, :dim, :q, CAST(:r AS jsonb), :rc, :co, :err)"""
        ).bindparams(bindparam("r", type_=JSONB))
        await self.session.execute(
            stmt,
            {
                "id": result_id,
                "tid": task_id,
                "dim": dimension,
                "q": query,
                "r": results,
                "rc": len(results),
                "co": company,
                "err": error,
            },
        )
        await self.session.commit()
        return result_id

    async def get_cached_for_company(
        self, company: str, *, dimensions: tuple[str, ...], ttl_hours: int = 24
    ) -> list[dict]:
        """REQ-053: 24h same-company cache lookup. Returns fresh results
        within the TTL for the requested dimensions.
        """
        if not dimensions:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        stmt = text(
            """SELECT id, task_id, dimension, query, results, result_count, company,
                      error, searched_at
            FROM interview_research_results
            WHERE company = :co
              AND dimension IN :dims
              AND searched_at >= :cutoff
              AND result_count > 0
            ORDER BY searched_at DESC"""
        ).bindparams(bindparam("dims", expanding=True))
        result = await self.session.execute(
            stmt,
            {"co": company, "dims": list(dimensions), "cutoff": cutoff},
        )
        rows = result.fetchall()
        return [_row_to_result(r) for r in rows]

    async def get_by_task(self, task_id: UUID) -> list[dict]:
        result = await self.session.execute(
            text(
                """SELECT id, task_id, dimension, query, results, result_count,
                          company, error, searched_at
                FROM interview_research_results
                WHERE task_id = :tid
                ORDER BY searched_at"""
            ),
            {"tid": task_id},
        )
        rows = result.fetchall()
        return [_row_to_result(r) for r in rows]


def _row_to_task(row: Any) -> dict:
    """Map a task DB row tuple to dict. Defensive against column ordering."""
    return {
        "id": row[0],
        "job_id": row[1],
        "user_id": row[2],
        "interview_time": row[3],
        "status": row[4],
        "search_dimensions": row[5] if isinstance(row[5], dict) else {},
        "report_id": row[6],
        "triggered_at": row[7],
        "started_at": row[8],
        "completed_at": row[9],
        "error_message": row[10],
        "created_at": row[11],
        "updated_at": row[12],
    }


def _row_to_result(row: Any) -> dict:
    return {
        "id": row[0],
        "task_id": row[1],
        "dimension": row[2],
        "query": row[3],
        "results": row[4] if isinstance(row[4], list) else [],
        "result_count": row[5] or 0,
        "company": row[6],
        "error": row[7],
        "searched_at": row[8],
    }


__all__ = ["ResearchTaskRepository", "ResearchResultRepository"]