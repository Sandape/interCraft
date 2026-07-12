"""ARQ: idempotent AI dispatch-intent confirmation (REQ-061 T023)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.db import get_session_context
from app.core.logging import get_logger
from app.modules.ai_runtime.models import AIDispatchIntent
from app.modules.ai_runtime.recovery.service import (
    DISPATCH_CONFIRMED,
    DISPATCH_DISPATCHING,
    DISPATCH_PENDING,
    RecoveryService,
    default_claim_owner,
)
from app.modules.ai_runtime.repository import ClaimGenerationConflict

log = get_logger("ai_runtime.dispatch_worker")


async def dispatch_ai_task_intent(ctx: dict[str, Any], intent_id: str) -> dict[str, str]:
    """Load intent, CAS-claim if needed, mark confirmed with transport_job_id.

    Idempotent: already-confirmed intents are a no-op. Redis/job identity is
    evidence only — the intent row remains authoritative.
    """
    tid = UUID(intent_id)
    job_try = ctx.get("job_try")
    job_id = None
    job = ctx.get("job")
    if job is not None:
        job_id = getattr(job, "job_id", None) or getattr(job, "id", None)
    if job_id is None:
        job_id = ctx.get("job_id")
    transport_job_id = str(job_id) if job_id is not None else f"arq:{intent_id}"

    owner = default_claim_owner()
    async with get_session_context() as session:
        recovery = RecoveryService(session, claim_owner=owner)
        result = await session.execute(
            select(AIDispatchIntent).where(AIDispatchIntent.id == tid)
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            log.warning("ai_runtime.dispatch.missing", intent_id=intent_id)
            return {"intent_id": intent_id, "status": "missing"}

        if intent.status == DISPATCH_CONFIRMED:
            return {
                "intent_id": intent_id,
                "status": DISPATCH_CONFIRMED,
                "transport_job_id": intent.transport_job_id or transport_job_id,
            }

        if intent.status == DISPATCH_PENDING:
            claimed = await recovery.claim_dispatch_intent(intent)
            if claimed is None:
                return {"intent_id": intent_id, "status": "claim_conflict"}
            if claimed.status != DISPATCH_DISPATCHING:
                return {"intent_id": intent_id, "status": claimed.status}
            intent = claimed

        if intent.status != DISPATCH_DISPATCHING:
            return {"intent_id": intent_id, "status": intent.status}

        try:
            confirmed = await recovery.confirm_dispatch_intent(
                intent_id=intent.id,
                expected_claim_generation=intent.claim_generation,
                transport_job_id=transport_job_id,
                claim_owner=owner,
            )
        except ClaimGenerationConflict:
            log.info(
                "ai_runtime.dispatch.confirm_conflict",
                intent_id=intent_id,
                job_try=job_try,
            )
            return {"intent_id": intent_id, "status": "claim_conflict"}

        log.info(
            "ai_runtime.dispatch.confirmed",
            intent_id=intent_id,
            transport_job_id=transport_job_id,
            claim_generation=confirmed.claim_generation,
        )
        return {
            "intent_id": intent_id,
            "status": DISPATCH_CONFIRMED,
            "transport_job_id": transport_job_id,
        }


__all__ = ["dispatch_ai_task_intent"]
