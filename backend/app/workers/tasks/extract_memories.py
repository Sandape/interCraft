"""ARQ task: extract_memories — extract semantic memories post-interview.

Triggered by app.modules.interviews.service after a 5-question interview
completes. Reads the interview state (position / company / interview_plan /
interview_report) and persists semantic facts to `semantic_memories`.

Best-effort: any failure is logged and swallowed. The interview completion
API response is already returned to the user by the time this runs.

Retries: 3 (WorkerSettings.max_tries). On final failure, the memory is
simply not stored — the next interview will run with degraded (no-memory)
context, which the planner handles gracefully (FR-013).
"""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import text

from app.core.db import get_session_context
from app.modules.agent_memory.extractor import extract_and_store
from app.modules.agent_memory.repository import AgentMemoryRepository

logger = structlog.get_logger("workers.extract_memories")


async def extract_memories(
    ctx: dict,
    user_id: str,
    session_id: str,
    state: dict,
) -> dict:
    """Extract semantic facts from interview `state` and persist them.

    ARQ calls this with positional (ctx, **kwargs). The kwargs match the
    names passed to `enqueue_job("extract_memories", user_id=...,
    session_id=..., state=...)`.

    `state` must be JSON-serializable (dict). Expected keys:
      - position: str | None
      - company: str | None
      - interview_plan: dict | None
      - interview_report: dict | None
      - overall_score: float | None
    """
    logger.info(
        "extract_memories.started",
        user_id=user_id,
        session_id=session_id,
    )
    try:
        async with get_session_context() as session:
            # Set RLS context so the repository can SELECT/INSERT for this user.
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": user_id},
            )
            repo = AgentMemoryRepository(session)
            summary = await extract_and_store(
                user_id=UUID(user_id),
                session_id=UUID(session_id),
                state=state,
                repo=repo,
            )
        logger.info(
            "extract_memories.completed",
            user_id=user_id,
            session_id=session_id,
            extracted=summary.get("extracted", 0),
            stored=summary.get("stored", 0),
            blocked=summary.get("blocked", 0),
        )
        return {"status": "ok", "user_id": user_id, "session_id": session_id, **summary}
    except Exception:
        logger.error(
            "extract_memories.failed",
            user_id=user_id,
            session_id=session_id,
            exc_info=True,
        )
        raise


__all__ = ["extract_memories"]
