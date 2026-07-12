"""REQ-061 Asia/Shanghai point bucket expiry worker (T050).

Expires unreserved available points on buckets past ``expires_at``. Reserved
quantities are preserved by ``PointMeteringService.expire``. Cross-day releases
into expired day buckets are converted to 24h compensation grants.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.modules.ai_metering.models import PointBucket
from app.modules.ai_metering.points.service import PointMeteringService, shanghai_business_date

log = get_logger("workers.ai_point_expiry")


def expiry_idempotency_key(bucket_id: UUID, *, at: datetime | None = None) -> str:
    moment = at or datetime.now(timezone.utc)
    biz = shanghai_business_date(moment)
    return f"expire:{bucket_id}:{biz.isoformat()}"


async def expire_due_buckets(
    session: AsyncSession,
    *,
    at: datetime | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Expire active buckets whose unreserved balance is past expiry."""
    moment = at or datetime.now(timezone.utc)
    result = await session.execute(
        select(PointBucket)
        .where(
            PointBucket.status == "active",
            PointBucket.expires_at <= moment,
            PointBucket.available_points > 0,
        )
        .order_by(PointBucket.expires_at.asc())
        .limit(limit)
    )
    buckets = list(result.scalars().all())
    svc = PointMeteringService(session)
    expired = 0
    reused = 0
    skipped = 0

    for bucket in buckets:
        try:
            outcome = await svc.expire(
                user_id=bucket.user_id,
                bucket_id=bucket.id,
                idempotency_key=expiry_idempotency_key(bucket.id, at=moment),
                reason="shanghai_day_boundary_expiry",
            )
            if outcome.reused:
                reused += 1
            else:
                expired += 1
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            log.warning(
                "ai_point_expiry.bucket_failed",
                bucket_id=str(bucket.id),
                error=str(exc),
            )

    return {
        "expired": expired,
        "reused": reused,
        "skipped": skipped,
        "scanned": len(buckets),
        "ts": moment.isoformat(),
    }


async def compensate_cross_day_release(
    session: AsyncSession,
    *,
    user_id: UUID,
    points: int,
    source_event_id: UUID | None = None,
    at: datetime | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Mint a 24h compensation bucket for a release into an expired day grant."""
    moment = at or datetime.now(timezone.utc)
    key = idempotency_key or f"compensate-cross-day:{user_id}:{moment.date().isoformat()}:{points}"
    svc = PointMeteringService(session)
    result = await svc.compensate(
        user_id=user_id,
        points=points,
        idempotency_key=key,
        expires_at=moment + timedelta(hours=24),
        reason="cross_day_expired_release_compensation",
        source_event_id=source_event_id,
    )
    return {
        "user_id": str(user_id),
        "points": points,
        "reused": result.reused,
        "event_id": str(result.event.id),
        "bucket_id": str(result.bucket.id) if result.bucket else None,
        "expires_at": (moment + timedelta(hours=24)).isoformat(),
    }


async def run_point_expiry(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cron entry: expire due daily-experience / compensation buckets."""
    _ = ctx
    now = datetime.now(timezone.utc)
    log.info("ai_point_expiry.start", ts=now.isoformat())

    factory = get_session_factory()
    async with factory() as session:
        summary = await expire_due_buckets(session, at=now)
        await session.commit()

    log.info("ai_point_expiry.done", **summary)
    return summary


async def ai_point_expiry(ctx: dict[str, Any]) -> dict[str, Any]:
    return await run_point_expiry(ctx)


__all__ = [
    "ai_point_expiry",
    "compensate_cross_day_release",
    "expire_due_buckets",
    "expiry_idempotency_key",
    "run_point_expiry",
]
