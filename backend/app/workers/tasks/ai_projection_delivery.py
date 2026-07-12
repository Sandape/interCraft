"""ARQ task: deliver pending AI telemetry projections (REQ-061 T022).

Session-per-task. Delivery only re-projects existing facts — no providers,
tools, domain writes, or metering commands.
"""

from __future__ import annotations

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.modules.ai_runtime.projections.service import ProjectionService

log = get_logger("workers.ai_projection_delivery")


async def deliver_ai_projections(ctx: dict) -> dict[str, int]:
    """Drain pending/retry_wait TelemetryProjectionDelivery rows."""
    limit = int(ctx.get("limit", 100)) if isinstance(ctx, dict) else 100
    factory = get_session_factory()
    async with factory() as session:
        service = ProjectionService(session)
        result = await service.deliver_pending(limit=limit)
        await session.commit()

    log.info(
        "deliver_ai_projections.done",
        claimed=result.get("claimed", 0),
        confirmed=result.get("confirmed", 0),
        retry_wait=result.get("retry_wait", 0),
        blocked=result.get("blocked", 0),
        abandoned=result.get("abandoned", 0),
    )
    return result


__all__ = ["deliver_ai_projections"]
