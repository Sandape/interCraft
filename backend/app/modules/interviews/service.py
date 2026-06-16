"""InterviewSessionService — Phase 4 full business logic."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.interview.graph import get_interview_graph
from app.modules.interviews.repository import InterviewSessionRepository
from app.modules.interviews.schemas import InterviewSessionCreate
from app.repositories.interview_report_repo import InterviewReportRepo

logger = structlog.get_logger(__name__)


class InterviewSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InterviewSessionRepository(session)

    async def list(self, user_id: UUID, **filters) -> list:
        return await self.repo.list(user_id, **filters)

    async def get(self, id: UUID, user_id: UUID) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        return session

    async def create(self, user_id: UUID, data: InterviewSessionCreate) -> dict:
        session = await self.repo.create(
            user_id=user_id,
            position=data.position,
            company=data.company,
            branch_id=data.branch_id,
            mode=data.mode,
        )

        # Use session.id as the LangGraph thread_id so that the WebSocket
        # handler (which only knows session_id) and the resume service both
        # look up the same checkpoint namespace. Generating a separate uuid4
        # here caused the resume API to find an empty state after restart.
        thread_id = str(session.id)

        await self.repo.update_status(session.id, "pending", thread_id=thread_id)
        return await self.repo.get(session.id, user_id)

    async def start(self, id: UUID, user_id: UUID) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status != "pending":
            raise HTTPException(status_code=409, detail=f"Cannot start interview with status '{session.status}'")

        now = datetime.now(UTC)
        await self.repo.update_status(id, "in_progress", started_at=now)

        return {
            "id": str(session.id),
            "status": "in_progress",
            "started_at": now.isoformat(),
        }

    async def get_report(self, id: UUID, user_id: UUID) -> dict | None:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status != "completed":
            return None

        report_repo = InterviewReportRepo(self.session)
        report = await report_repo.get_by_session_id(id)
        if report is None:
            return None
        report_dict = report.model_dump()

        per_q = report_dict.get("per_question_score", []) or []
        needs_backfill = any(
            isinstance(q, dict) and not q.get("question_text")
            for q in per_q
        )
        if needs_backfill:
            from app.agents.checkpointer import get_graph_config
            from app.agents.interview.graph import get_interview_graph

            # Historical bug: checkpoints are stored under session_id, not the
            # recorded thread_id. Try both keys for safety.
            lookup_keys = [str(id)]
            if session.thread_id and str(session.thread_id) != str(id):
                lookup_keys.append(str(session.thread_id))

            try:
                graph = await get_interview_graph().build_graph()
                questions = None
                user_answers = None
                for key in lookup_keys:
                    try:
                        state = await graph.aget_state(await get_graph_config(key))
                    except Exception:
                        continue
                    values = state.values if state.values else {}
                    qs = values.get("questions") or []
                    if not qs:
                        continue
                    questions = qs
                    msgs = values.get("messages") or []
                    user_answers = [
                        (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "") or "")
                        for m in msgs
                        if (isinstance(m, dict) and m.get("role") == "user")
                        or (not isinstance(m, dict) and getattr(m, "type", "") == "human")
                    ]
                    break

                if questions:
                    # user_answers[0] is the self-intro at the intake step. Skip it.
                    answers_for_q = user_answers[1:1 + len(questions)] if user_answers else []
                    for i, q in enumerate(per_q):
                        if not isinstance(q, dict):
                            continue
                        if not q.get("question_text") and i < len(questions):
                            q["question_text"] = questions[i].get("question", "")
                        if not q.get("user_answer") and i < len(answers_for_q):
                            q["user_answer"] = answers_for_q[i]
                    report_dict["per_question_score"] = per_q
            except Exception:
                # On any error, return the report as-is — UI shows fallback placeholders.
                pass

        return report_dict

    async def submit_answer(self, id: UUID, user_id: UUID, answer: str, sequence_no: int) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status != "in_progress":
            raise HTTPException(status_code=409, detail=f"Cannot submit answer for status '{session.status}'")

        thread_id = session.thread_id
        if not thread_id:
            raise HTTPException(status_code=400, detail="No active interview thread")

        graph = get_interview_graph()
        try:
            result = await graph.submit_answer(
                thread_id=thread_id,
                answer=answer,
                sequence_no=sequence_no,
                user_id=str(user_id),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}") from exc

        # Check if interview completed
        scores = result.get("scores", [])
        if len(scores) >= 5:
            overall = result.get("overall_score", 0)
            now = datetime.now(UTC)
            started = session.started_at
            duration = int((now - started).total_seconds()) if started else 0
            await self.repo.update_status(
                id, "completed", ended_at=now, duration_sec=duration, overall_score=float(overall)
            )

            # Write report
            report_data = result.get("interview_report", {})
            if report_data:
                from app.domain.interview_report import InterviewReportCreate
                report_repo = InterviewReportRepo(self.session)
                await report_repo.create(InterviewReportCreate(
                    overall_score=float(overall),
                    per_question_score=report_data.get("per_question_score", []),
                    dimension_scores=report_data.get("dimension_scores", {}),
                    strengths=report_data.get("strengths", []),
                    improvements=report_data.get("improvements", []),
                    summary_md=report_data.get("summary_md", ""),
                    session_id=id,
                ))

            # Synchronously upsert per-dimension scores so /ability-profile
            # reflects the new scores immediately. The async arq job below
            # still runs for LLM-generated insights and history snapshots.
            await self._sync_ability_dimensions(id, user_id)

            # Enqueue ability diagnosis so the dashboard reflects interview scores.
            # Best-effort — failure here must not fail the API request.
            try:
                from app.core.redis import enqueue_job
                await enqueue_job(
                    "ability_diagnose",
                    user_id=str(user_id),
                    session_id=str(id),
                )
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    "ability_diagnose.enqueue_failed", exc_info=True
                )

        return result

    async def delete(self, id: UUID, user_id: UUID) -> None:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        deleted = await self.repo.soft_delete(id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Interview session not found")

    async def _sync_ability_dimensions(self, session_id: UUID, user_id: UUID) -> None:
        """Synchronously upsert per-dimension scores from the interview report
        into `ability_dimensions` so `/ability-profile` reflects the new scores
        immediately after interview completion — no waiting on the async ARQ
        `ability_diagnose` worker.

        Mirrors `app.agents.nodes.ability_diagnose.update_dimensions` but is
        synchronous and LLM-free. Failures are logged and swallowed: an ability
        sync failure MUST NOT fail the interview completion request.
        """
        try:
            report = await InterviewReportRepo(self.session).get_by_session_id(session_id)
            if report is None:
                logger.warning(
                    "interview.ability_sync.no_report",
                    session_id=str(session_id),
                    user_id=str(user_id),
                )
                return

            dimension_scores = report.dimension_scores or {}
            if not dimension_scores:
                logger.warning(
                    "interview.ability_sync.empty_dimensions",
                    session_id=str(session_id),
                    user_id=str(user_id),
                )
                return

            await self.session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )

            upsert_dim = text(
                """INSERT INTO ability_dimensions
                (id, user_id, dimension_key, actual_score, ideal_score,
                 sub_scores, is_active, source, last_updated_at,
                 created_at, updated_at)
                VALUES (:id, :uid, :dim, :score, 10, '{}'::jsonb,
                        true, 'interview', :now, :now, :now)
                ON CONFLICT (user_id, dimension_key) DO UPDATE
                SET actual_score = EXCLUDED.actual_score,
                    source = 'interview',
                    last_updated_at = EXCLUDED.last_updated_at,
                    updated_at = EXCLUDED.updated_at"""
            )

            now = datetime.now(UTC)
            for dim_key, score in dimension_scores.items():
                await self.session.execute(
                    upsert_dim,
                    {
                        "id": uuid4(),
                        "uid": user_id,
                        "dim": dim_key,
                        "score": Decimal(str(score)),
                        "now": now,
                    },
                )

            await self.session.commit()
            logger.info(
                "interview.ability_sync.completed",
                session_id=str(session_id),
                user_id=str(user_id),
                dimensions=list(dimension_scores.keys()),
            )
        except Exception:
            logger.error(
                "interview.ability_sync.failed",
                session_id=str(session_id),
                user_id=str(user_id),
                exc_info=True,
            )

    async def resume(self, id: UUID, user_id: UUID) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="Interview already completed")
        if session.status == "expired":
            raise HTTPException(status_code=410, detail="Interview session expired")

        thread_id = session.thread_id
        if not thread_id:
            raise HTTPException(status_code=400, detail="No active interview thread")

        graph = get_interview_graph()
        # Try session_id first (WebSocket handler always writes under
        # session_id, and new sessions store thread_id == session_id).
        # Fall back to the recorded thread_id for backwards compat with
        # legacy sessions whose thread_id was a separate uuid4.
        candidate_keys: list[str] = []
        for key in (str(id), str(thread_id)):
            if key and key not in candidate_keys:
                candidate_keys.append(key)

        for key in candidate_keys:
            state = await graph.get_current_state(key)
            if state and state.get("values"):
                return state
        # No state found under either key — return empty state with current key
        return await graph.get_current_state(candidate_keys[0])


__all__ = ["InterviewSessionService"]
