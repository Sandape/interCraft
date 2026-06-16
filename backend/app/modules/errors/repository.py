"""ErrorQuestionRepository — CRUD for error_questions."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.errors.models import ErrorQuestion


class ErrorQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        user_id: UUID,
        *,
        dimension: str | None = None,
        status: str | None = None,
        frequency_min: int = 0,
        source: str | None = None,
        limit: int = 20,
        order_by: str = "-created_at",
    ) -> list[ErrorQuestion]:
        stmt = select(ErrorQuestion).where(
            ErrorQuestion.user_id == user_id,
            ErrorQuestion.deleted_at.is_(None),
        )
        if dimension:
            stmt = stmt.where(ErrorQuestion.dimension == dimension)
        if status:
            stmt = stmt.where(ErrorQuestion.status == status)
        if frequency_min > 0:
            stmt = stmt.where(ErrorQuestion.frequency >= frequency_min)
        if source == "auto":
            stmt = stmt.where(ErrorQuestion.source_session_id.isnot(None))
        elif source == "manual":
            stmt = stmt.where(ErrorQuestion.source_session_id.is_(None))

        # Default sort: status ASC, frequency DESC, created_at DESC
        stmt = stmt.order_by(
            ErrorQuestion.status.asc(),
            ErrorQuestion.frequency.desc(),
            ErrorQuestion.created_at.desc(),
        ).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, id: UUID, user_id: UUID) -> ErrorQuestion | None:
        stmt = select(ErrorQuestion).where(
            ErrorQuestion.id == id,
            ErrorQuestion.user_id == user_id,
            ErrorQuestion.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, instance: ErrorQuestion) -> ErrorQuestion:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    # 019 — UPSERT via partial unique index on source_question_id
    # This allows the interview score node to re-sink the same question
    # (e.g. on re-score) without raising a duplicate-key error.
    UPSERT_SQL = text("""
        INSERT INTO error_questions
            (id, user_id, source_session_id, source_question_id,
             dimension, question_text, answer_text, score,
             status, frequency, created_at, updated_at)
        VALUES
            (:id, :user_id, :source_session_id, :source_question_id,
             :dimension, :question_text, :answer_text, :score,
             'fresh', 3, now(), now())
        ON CONFLICT (source_question_id)
        WHERE source_question_id IS NOT NULL
        DO UPDATE SET
            score         = EXCLUDED.score,
            answer_text   = EXCLUDED.answer_text,
            frequency     = 3,
            status        = 'fresh',
            updated_at    = now()
        RETURNING *
    """)

    async def upsert_by_source(
        self,
        user_id: UUID,
        source_session_id: UUID,
        source_question_id: UUID,
        question_text: str,
        answer_text: str,
        dimension: str,
        score: int,
    ) -> ErrorQuestion:
        from uuid import uuid4

        result = await self.session.execute(
            self.UPSERT_SQL,
            {
                "id": uuid4(),
                "user_id": user_id,
                "source_session_id": source_session_id,
                "source_question_id": source_question_id,
                "dimension": dimension,
                "question_text": question_text[:2000],
                "answer_text": answer_text,
                "score": score,
            },
        )
        row = result.fetchone()
        await self.session.flush()
        # Return a fresh model instance from the returned row
        return ErrorQuestion(**row._mapping) if row else None

    async def patch(self, id: UUID, user_id: UUID, patch_data: dict) -> ErrorQuestion | None:
        instance = await self.get(id, user_id)
        if instance is None:
            return None
        for k, v in patch_data.items():
            if hasattr(instance, k) and v is not None:
                setattr(instance, k, v)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def clear_source(self, id: UUID, user_id: UUID) -> ErrorQuestion | None:
        """Set source_session_id and source_question_id to NULL."""
        from sqlalchemy import update

        stmt = (
            update(ErrorQuestion)
            .where(ErrorQuestion.id == id, ErrorQuestion.user_id == user_id)
            .values(source_session_id=None, source_question_id=None, updated_at=datetime.now(timezone.utc))
            .returning(ErrorQuestion)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        row = result.fetchone()
        return row[0] if row else None

    async def soft_delete(self, id: UUID, user_id: UUID) -> bool:
        instance = await self.get(id, user_id)
        if instance is None:
            return False
        instance.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def reset(self, id: UUID, user_id: UUID) -> ErrorQuestion | None:
        instance = await self.get(id, user_id)
        if instance is None:
            return None
        instance.status = "fresh"
        instance.frequency = 3
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def recall(self, id: UUID, user_id: UUID) -> ErrorQuestion | None:
        instance = await self.get(id, user_id)
        if instance is None:
            return None

        next_frequency = max(instance.frequency - 1, 0)
        instance.frequency = next_frequency
        if next_frequency == 0:
            instance.status = "mastered"
        elif next_frequency < 3:
            instance.status = "practicing"
        else:
            instance.status = "fresh"
        instance.last_practiced_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


__all__ = ["ErrorQuestionRepository"]
