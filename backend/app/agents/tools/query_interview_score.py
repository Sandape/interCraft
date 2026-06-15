"""Tool: query_interview_score — read interview_reports + ai_messages (shared by M18).

Used by the Ability Diagnose subgraph to aggregate scores after an interview.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import text

from app.core.db import get_session_factory

logger = structlog.get_logger("agents.tools.query_interview_score")


async def query_interview_report(session_id: str) -> dict | None:
    """Fetch the interview report for a given session."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                """SELECT id, session_id, overall_score, per_question_score,
                dimension_scores, strengths, improvements, summary_md,
                generated_at, created_at
                FROM interview_reports WHERE session_id = :sid"""
            ),
            {"sid": UUID(session_id)},
        )
        row = result.fetchone()
        if row is None:
            return None
        return {
            "id": str(row[0]),
            "session_id": str(row[1]),
            "overall_score": float(row[2]) if row[2] is not None else None,
            "per_question_score": row[3] if isinstance(row[3], list) else [],
            "dimension_scores": row[4] if isinstance(row[4], dict) else {},
            "strengths": row[5] if isinstance(row[5], list) else [],
            "improvements": row[6] if isinstance(row[6], list) else [],
            "summary_md": row[7] or "",
            "generated_at": row[8].isoformat() if row[8] else None,
            "created_at": row[9].isoformat() if row[9] else None,
        }


async def query_ai_messages_for_session(session_id: str) -> list[dict]:
    """Fetch ai_messages for a given session (thread_id)."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                """SELECT id, node_name, role, model, prompt_tokens, completion_tokens,
                duration_ms, created_at
                FROM ai_messages WHERE thread_id = :tid
                ORDER BY created_at ASC"""
            ),
            {"tid": session_id},
        )
        rows = result.fetchall()
        return [
            {
                "id": str(r[0]),
                "node_name": r[1],
                "role": r[2],
                "model": r[3],
                "prompt_tokens": r[4] or 0,
                "completion_tokens": r[5] or 0,
                "duration_ms": r[6] or 0,
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]


async def query_interview_questions(session_id: str) -> list[dict]:
    """Fetch interview questions for a session from interview_questions table."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            result = await session.execute(
                text(
                    """SELECT id, session_id, question_no, question_text, dimension,
                    expected_points, score, feedback, created_at
                    FROM interview_questions WHERE session_id = :sid
                    ORDER BY question_no ASC"""
                ),
                {"sid": UUID(session_id)},
            )
            rows = result.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "session_id": str(r[1]),
                    "question_no": r[2],
                    "question_text": r[3],
                    "dimension": r[4],
                    "expected_points": r[5] if isinstance(r[5], list) else [],
                    "score": r[6],
                    "feedback": r[7],
                    "created_at": r[8].isoformat() if r[8] else None,
                }
                for r in rows
            ]
        except Exception:
            # Table may not exist in all environments
            return []


__all__ = [
    "query_ai_messages_for_session",
    "query_interview_questions",
    "query_interview_report",
]
