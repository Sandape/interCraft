"""ARQ task: provenance deletion fan-out (REQ-061 T022).

Session-per-task. Processes pending AIDataDeletionDelivery rows against the
lifecycle policy registry. No external provider I/O inside the held transaction.
"""

from __future__ import annotations

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.modules.ai_runtime.privacy.service import PrivacyService

log = get_logger("workers.ai_data_deletion")


async def run_ai_data_deletion(ctx: dict) -> dict[str, int]:
    """Run bounded deletion fan-out steps for pending deliveries."""
    limit = int(ctx.get("limit", 100)) if isinstance(ctx, dict) else 100
    factory = get_session_factory()
    async with factory() as session:
        service = PrivacyService(session)
        result = await service.run_pending(limit=limit)
        await session.commit()

    log.info(
        "run_ai_data_deletion.done",
        claimed=result.get("claimed", 0),
        confirmed=result.get("confirmed", 0),
        expired=result.get("expired", 0),
        not_supported=result.get("not_supported_with_contract_expiry", 0),
        retry_wait=result.get("retry_wait", 0),
        sla_alerts=result.get("sla_alerts", 0),
    )
    return result


__all__ = ["run_ai_data_deletion"]
