"""Owner-scoped recovery for expired REQ-060 Agent task claims."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_session_context
from app.core.logging import get_logger
from app.modules.agent.repository import AgentTaskRepository

log = get_logger("agent.task_recovery")


async def scan_agent_task_recovery(
    ctx: dict[str, Any], *, max_count: int = 100
) -> dict[str, int]:
    """Discover only identifiers through the narrow SECURITY DEFINER surface."""
    bounded = min(max(int(max_count), 1), 1000)
    async with get_session_context() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT task_id, user_id "
                    "FROM public.get_agent_task_recovery_candidates(:max_count)"
                ),
                {"max_count": bounded},
            )
        ).all()

    redis = ctx.get("redis")
    enqueued = 0
    if redis is None:
        log.error("agent.task_recovery.scan_failed", reason="redis_unavailable")
        return {"candidates": len(rows), "enqueued": 0}
    for task_id, user_id in rows:
        job = await redis.enqueue_job(
            "recover_agent_task", str(user_id), str(task_id)
        )
        if job is not None:
            enqueued += 1
    log.info(
        "agent.task_recovery.scanned",
        candidates=len(rows),
        enqueued=enqueued,
    )
    return {"candidates": len(rows), "enqueued": enqueued}


async def recover_agent_task(
    ctx: dict[str, Any], user_id: str, task_id: str
) -> dict[str, str]:
    """Recover one task under its tenant RLS context and append an audit event."""
    uid = UUID(user_id)
    tid = UUID(task_id)
    settings = get_settings()
    async with get_session_context(user_id=uid) as session:
        task = await AgentTaskRepository(session).recover_expired_task(
            uid,
            tid,
            max_attempts=settings.wechat_agent_max_attempts,
        )
    if task is None:
        return {"task_id": str(tid), "status": "unchanged"}
    log.info(
        "agent.task_recovery.completed",
        task_id=str(task.id),
        status=task.status,
        claim_generation=task.claim_generation,
    )
    return {"task_id": str(task.id), "status": task.status}


__all__ = ["recover_agent_task", "scan_agent_task_recovery"]

