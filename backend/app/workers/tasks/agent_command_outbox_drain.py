"""Dispatch Agent domain commands written atomically with Tool effects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text

from app.core.config import get_settings
from app.core.db import get_db_session_no_rls, get_session_context
from app.core.logging import get_logger
from app.core.redis import enqueue_job
from app.modules.agent.models import AgentCommandDispatchQueue, AgentCommandOutbox

log = get_logger("workers.agent_command_outbox_drain")


async def agent_command_outbox_drain(ctx: dict) -> dict[str, int]:
    """Claim and dispatch pending commands with stable provider job IDs."""
    candidates: list[tuple[UUID, UUID]] = []
    async for session in get_db_session_no_rls():
        rows = await session.execute(
            text(
                "SELECT outbox_id, user_id FROM agent_command_dispatch_queue "
                "WHERE available_at <= now() ORDER BY created_at LIMIT 100"
            )
        )
        candidates = [(row[0], row[1]) for row in rows]
        break

    dispatched = 0
    retried = 0
    dead = 0
    for outbox_id, user_id in candidates:
        outcome = await _dispatch_one(outbox_id=outbox_id, user_id=user_id)
        if outcome == "dispatched":
            dispatched += 1
        elif outcome == "retry_wait":
            retried += 1
        elif outcome == "dead_letter":
            dead += 1
    return {"dispatched": dispatched, "retried": retried, "dead": dead}


async def _dispatch_one(*, outbox_id: UUID, user_id: UUID) -> str:
    settings = get_settings()
    owner_id = uuid4()
    now = datetime.now(UTC)
    async with get_session_context(user_id=user_id) as session:
        command = await session.scalar(
            select(AgentCommandOutbox)
            .where(
                AgentCommandOutbox.id == outbox_id,
                AgentCommandOutbox.user_id == user_id,
                AgentCommandOutbox.status.in_(["pending", "retry_wait", "claimed"]),
                (AgentCommandOutbox.next_attempt_at.is_(None))
                | (AgentCommandOutbox.next_attempt_at <= now),
                (AgentCommandOutbox.claim_until.is_(None))
                | (AgentCommandOutbox.claim_until <= now),
            )
            .with_for_update(skip_locked=True)
        )
        if command is None:
            return "skipped"
        command.status = "claimed"
        command.claim_owner = owner_id
        command.claim_until = now + timedelta(
            seconds=settings.wechat_agent_message_claim_seconds
        )
        command.attempt_count += 1
        await session.flush()

        try:
            if command.command_type != "resume_derive.execute":
                raise ValueError("unsupported_command_type")
            run_id = str(command.payload_json["run_id"])
            payload_user_id = str(command.payload_json["user_id"])
            if payload_user_id != str(user_id) or run_id != str(command.aggregate_id):
                raise ValueError("command_payload_authority_mismatch")
            await enqueue_job(
                "execute_resume_derive",
                run_id=run_id,
                user_id=str(user_id),
                _job_id=run_id,
            )
        except Exception as exc:
            command.claim_owner = None
            command.claim_until = None
            command.error_category = type(exc).__name__
            if command.attempt_count >= settings.wechat_agent_max_attempts:
                command.status = "dead_letter"
                outcome = "dead_letter"
            else:
                command.status = "retry_wait"
                command.next_attempt_at = datetime.now(UTC) + timedelta(
                    seconds=min(300, 2 ** min(command.attempt_count, 8))
                )
                await session.execute(
                    text(
                        "UPDATE agent_command_dispatch_queue SET available_at=:at "
                        "WHERE outbox_id=:outbox_id AND user_id=:user_id"
                    ),
                    {
                        "at": command.next_attempt_at,
                        "outbox_id": outbox_id,
                        "user_id": user_id,
                    },
                )
                outcome = "retry_wait"
            log.warning(
                "agent_command_dispatch_failed",
                extra={"command_type": command.command_type, "error_type": type(exc).__name__},
            )
            return outcome

        command.status = "dispatched"
        command.claim_owner = None
        command.claim_until = None
        command.next_attempt_at = None
        command.error_category = None
        command.dispatched_at = datetime.now(UTC)
        await session.execute(
            delete(AgentCommandDispatchQueue).where(
                AgentCommandDispatchQueue.outbox_id == outbox_id,
                AgentCommandDispatchQueue.user_id == user_id,
            )
        )
        return "dispatched"


__all__ = ["agent_command_outbox_drain"]
