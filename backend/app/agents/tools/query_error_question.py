"""Tool: query_error_question_by_id — fetch a single error question (shared by M17).

Wraps ErrorQuestionRepository.get.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from langchain_core.tools import tool

from app.core.db import get_session_factory
from app.modules.errors.repository import ErrorQuestionRepository

logger = structlog.get_logger("agents.tools.query_error_question")


@tool
async def query_error_question_by_id(
    error_question_id: str,
    *,
    user_id: str | None = None,
) -> dict | None:
    """Fetch a single error question by ID.

    Returns a dict representation, or None if not found.
    """
    factory = get_session_factory()
    async with factory() as session:
        if user_id:
            from app.domain.rls import set_user_context

            await set_user_context(session, user_id)

        repo = ErrorQuestionRepository(session)
        eq = await repo.get(UUID(error_question_id), UUID(user_id) if user_id else UUID(int=0))

        if eq is None:
            return None

        return {
            "id": str(eq.id),
            "user_id": str(eq.user_id),
            "source_session_id": str(eq.source_session_id) if eq.source_session_id else None,
            "dimension": eq.dimension,
            "question_text": eq.question_text,
            "answer_text": eq.answer_text,
            "reference_answer_md": eq.reference_answer_md,
            "score": eq.score,
            "status": eq.status,
            "frequency": eq.frequency,
            "tags": eq.tags,
            "created_at": eq.created_at.isoformat() if eq.created_at else None,
        }


__all__ = ["query_error_question_by_id"]
