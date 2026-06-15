"""ErrorCoachService — decrement frequency and update error question status.

Used by M17 Error Coach subgraph for DB operations.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import text

from app.core.db import get_session_factory
from app.domain.rls import set_user_context

logger = structlog.get_logger("services.error_coach")


class ErrorCoachService:
    """Service layer for M17 operations."""

    async def decrement_frequency(self, error_question_id: str, user_id: str) -> dict:
        """Decrement error_question frequency by 1. If frequency reaches 0, set status to 'mastered'.

        Returns the updated question data.
        """
        factory = get_session_factory()
        async with factory() as session:
            await set_user_context(session, user_id)
            eq_id = UUID(error_question_id)

            # Get current frequency
            result = await session.execute(
                text("SELECT frequency, status FROM error_questions WHERE id = :id"),
                {"id": eq_id},
            )
            row = result.fetchone()
            if row is None:
                logger.warning("error_question_not_found", id=error_question_id)
                return {"status": "not_found"}

            current_freq = row[0] or 0
            new_freq = max(0, current_freq - 1)
            new_status = "mastered" if new_freq == 0 else row[1]

            await session.execute(
                text(
                    """UPDATE error_questions
                    SET frequency = :freq, status = :status, updated_at = now()
                    WHERE id = :id"""
                ),
                {"freq": new_freq, "status": new_status, "id": eq_id},
            )
            await session.commit()

            return {
                "id": error_question_id,
                "frequency": new_freq,
                "status": new_status,
            }


__all__ = ["ErrorCoachService"]
