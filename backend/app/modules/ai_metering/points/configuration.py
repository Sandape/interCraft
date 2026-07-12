"""REQ-061 versioned daily grant configuration (T049).

In-memory publish/resolve helpers pin unit-test behaviour. Workers and the
metering API reuse the same planning helpers (idempotency key, Shanghai
business date, no retroactive resize) when writing durable grant rows via
``PointMeteringService`` and ``DailyGrantConfigVersion``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID
from zoneinfo import ZoneInfo

from app.modules.ai_metering.points.catalog import INITIAL_DAILY_GRANT_POINTS
from app.modules.ai_metering.points.ledger import (
    LedgerError,
    PointBucket,
    PointLedger,
    apply_command,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_GRANT_VERSION = "daily-grant-v1"

_CONFIG_STORE: list[GrantConfig] = []
_VERSION_SEQ = 0


@dataclass(frozen=True, slots=True)
class GrantConfigDraft:
    points_amount: int
    effective_at: datetime
    actor_id: str
    reason: str | None = None
    timezone: str = DEFAULT_TIMEZONE


@dataclass(frozen=True, slots=True)
class GrantConfig:
    version: str
    points_amount: int
    timezone: str
    effective_at: datetime
    status: str
    actor_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DailyGrantPlan:
    should_grant: bool
    points: int
    business_date: date
    idempotency_key: str
    immediate: bool
    grant_config_version: str
    expires_at: datetime
    timezone: str = DEFAULT_TIMEZONE


def _ensure_aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def shanghai_business_date(at: datetime | None = None) -> date:
    moment = _ensure_aware(at or datetime.now(timezone.utc))
    return moment.astimezone(SHANGHAI).date()


def shanghai_day_expiry(business_date: date) -> datetime:
    """Bucket expires at the next Asia/Shanghai midnight (start of next day)."""
    next_day = business_date + timedelta(days=1)
    local = datetime(
        next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=SHANGHAI
    )
    return local.astimezone(timezone.utc)


def reset_grant_config_store() -> None:
    """Test helper — clear published in-memory configs."""
    global _VERSION_SEQ
    _CONFIG_STORE.clear()
    _VERSION_SEQ = 0


def publish_grant_config(draft: GrantConfigDraft) -> GrantConfig:
    """Publish a new grant config version (in-memory; does not mutate past grants)."""
    global _VERSION_SEQ
    if draft.points_amount < 0:
        raise ValueError("points_amount must be >= 0")
    _VERSION_SEQ += 1
    cfg = GrantConfig(
        version=f"daily-grant-v{_VERSION_SEQ}",
        points_amount=draft.points_amount,
        timezone=draft.timezone or DEFAULT_TIMEZONE,
        effective_at=_ensure_aware(draft.effective_at),
        status="active",
        actor_id=draft.actor_id,
        reason=draft.reason,
    )
    _CONFIG_STORE.append(cfg)
    return cfg


def resolve_effective_grant_config(*, at: datetime | None = None) -> GrantConfig:
    """Return the active config whose ``effective_at`` is the latest ≤ ``at``."""
    moment = _ensure_aware(at or datetime.now(timezone.utc))
    eligible = [
        c
        for c in _CONFIG_STORE
        if c.status == "active" and _ensure_aware(c.effective_at) <= moment
    ]
    if not eligible:
        return GrantConfig(
            version=DEFAULT_GRANT_VERSION,
            points_amount=INITIAL_DAILY_GRANT_POINTS,
            timezone=DEFAULT_TIMEZONE,
            effective_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            status="active",
            reason="bootstrap default",
        )
    eligible.sort(key=lambda c: _ensure_aware(c.effective_at))
    return eligible[-1]


def daily_grant_idempotency_key(user_id: str | UUID, business_date: date) -> str:
    return f"daily-grant:{user_id}:{business_date.isoformat()}"


def plan_daily_grant(
    *,
    user_id: str | UUID,
    business_date: date,
    at: datetime | None = None,
    is_new_user: bool = False,
    already_granted: bool = False,
) -> DailyGrantPlan:
    """Plan one Shanghai-day experience grant (idempotent key, full amount)."""
    moment = _ensure_aware(at or datetime.now(timezone.utc))
    cfg = resolve_effective_grant_config(at=moment)
    expires = shanghai_day_expiry(business_date)
    key = daily_grant_idempotency_key(user_id, business_date)
    if already_granted:
        return DailyGrantPlan(
            should_grant=False,
            points=cfg.points_amount,
            business_date=business_date,
            idempotency_key=key,
            immediate=is_new_user,
            grant_config_version=cfg.version,
            expires_at=expires,
            timezone=cfg.timezone,
        )
    return DailyGrantPlan(
        should_grant=True,
        points=cfg.points_amount,
        business_date=business_date,
        idempotency_key=key,
        immediate=bool(is_new_user),
        grant_config_version=cfg.version,
        expires_at=expires,
        timezone=cfg.timezone,
    )


def resize_existing_grants(
    *,
    buckets: Sequence[dict[str, Any]],
    new_points_amount: int,
    at: datetime | None = None,
) -> None:
    """Config changes must never mutate already-granted buckets."""
    _ = (buckets, new_points_amount, at)
    raise PermissionError(
        "daily grant config changes must not resize already-granted buckets"
    )


def expire_unreserved_buckets(
    ledger: PointLedger,
    *,
    at: datetime,
    idempotency_key: str,
) -> PointLedger:
    """Zero remaining points on buckets whose ``expires_at`` has passed.

    Reserved quantities live on the ledger reservation projection and are not
    wiped by day-boundary expiry (cross-day reservation survival).
    """
    if idempotency_key in ledger._seen_keys:
        return ledger

    moment = _ensure_aware(at)
    new_buckets: list[PointBucket] = []
    for bucket in ledger.buckets:
        if bucket.expires_at <= moment and bucket.remaining_points > 0:
            new_buckets.append(replace(bucket, remaining_points=0))
        else:
            new_buckets.append(bucket)

    seen = dict(ledger._seen_keys)
    seen[idempotency_key] = "expire"
    return PointLedger(
        user_id=ledger.user_id,
        buckets=new_buckets,
        events=list(ledger.events),
        reserved=ledger.reserved,
        last_reservation_id=ledger.last_reservation_id,
        _reservations=dict(ledger._reservations),
        _seen_keys=seen,
    )


def compensate_expired_release(
    ledger: PointLedger,
    *,
    points: int,
    reservation_id: str,
    source_bucket_id: str,
    idempotency_key: str,
    now: datetime | None = None,
) -> PointLedger:
    """Convert a release into an expired day bucket into a 24h compensation grant."""
    if points <= 0:
        raise LedgerError("compensation points must be positive")
    moment = _ensure_aware(now or datetime.now(timezone.utc))
    expires_at = moment + timedelta(hours=24)

    reservations = dict(ledger._reservations)
    open_amt = reservations.get(reservation_id, 0)
    if open_amt < points:
        # Allow compensate when reserved was tracked only on ledger.reserved.
        if ledger.reserved < points:
            raise LedgerError("compensation exceeds open reservation")
    else:
        reservations[reservation_id] = open_amt - points

    reserved = max(0, ledger.reserved - points)
    interim = PointLedger(
        user_id=ledger.user_id,
        buckets=list(ledger.buckets),
        events=list(ledger.events),
        reserved=reserved,
        last_reservation_id=ledger.last_reservation_id,
        _reservations=reservations,
        _seen_keys=dict(ledger._seen_keys),
    )
    _ = source_bucket_id  # retained for audit linkage by callers
    return apply_command(
        interim,
        command="compensate",
        points=points,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
        business_date="compensation",
    )


__all__ = [
    "DEFAULT_GRANT_VERSION",
    "DEFAULT_TIMEZONE",
    "DailyGrantPlan",
    "GrantConfig",
    "GrantConfigDraft",
    "SHANGHAI",
    "compensate_expired_release",
    "daily_grant_idempotency_key",
    "expire_unreserved_buckets",
    "plan_daily_grant",
    "publish_grant_config",
    "reset_grant_config_store",
    "resize_existing_grants",
    "resolve_effective_grant_config",
    "shanghai_business_date",
    "shanghai_day_expiry",
]
