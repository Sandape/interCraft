"""Phase 6 — Subscription service: beta entitlement/point projection + legacy quota."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.account.beta_entitlement import get_beta_entitlement
from app.modules.auth.models import User
from app.modules.content.models import SubscriptionPlan


class SubscriptionError(Exception):
    pass


class SubscriptionService:
    """Subscription plan info, quota checks, pre-check for interview start.

    Public reads project REQ-061 beta entitlement + point balances.
    Legacy monthly-token comparison is retained for internal pre-check only.
    """

    def __init__(self, db: AsyncSession, user_id: UUID | None = None) -> None:
        self.db = db
        self.user_id = user_id

    async def list_plans(self) -> list[SubscriptionPlan]:
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    def _legacy_monthly_token_status(self, user: User) -> dict:
        """Internal monthly-token projection (not the beta UX source of truth)."""
        remaining = user.monthly_token_quota - user.monthly_token_used
        usage_pct = round((user.monthly_token_used / max(user.monthly_token_quota, 1)) * 100, 1)

        now = datetime.now(timezone.utc)
        if now.month == 12:
            reset_date = now.replace(
                year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            reset_date = now.replace(
                month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
            )

        return {
            "plan": user.subscription,
            "monthly_token_quota": user.monthly_token_quota,
            "monthly_token_used": user.monthly_token_used,
            "monthly_token_remaining": max(remaining, 0),
            "usage_pct": usage_pct,
            "reset_date": reset_date,
            "can_start_interview": remaining > 0,
        }

    async def _point_projection(self) -> dict:
        """Owner point account projection for subscription/settings surfaces."""
        from app.modules.ai_metering.points.catalog import INITIAL_DAILY_GRANT_POINTS
        from app.modules.ai_metering.points.configuration import (
            resolve_effective_grant_config,
            shanghai_business_date,
        )
        from app.modules.ai_metering.repository import PointMeteringRepository

        assert self.user_id is not None
        repo = PointMeteringRepository(self.db)
        account = await repo.get_or_create_account(self.user_id)
        buckets = await repo.list_buckets_for_user(self.user_id)
        now = datetime.now(timezone.utc)
        active = [b for b in buckets if b.status == "active" and b.expires_at > now]
        cfg = resolve_effective_grant_config(at=now)

        next_expiry: datetime | None = None
        bucket_outs: list[dict] = []
        for bucket in active:
            if next_expiry is None or bucket.expires_at < next_expiry:
                next_expiry = bucket.expires_at
            btype = bucket.bucket_type
            if btype not in {"daily_experience", "compensation"}:
                btype = "daily_experience"
            bucket_outs.append(
                {
                    "bucket_id": str(bucket.id),
                    "bucket_type": btype,
                    "available": bucket.available_points,
                    "reserved": bucket.reserved_points,
                    "expires_at": bucket.expires_at,
                    "business_date": bucket.business_date.isoformat()
                    if bucket.business_date is not None
                    else None,
                }
            )

        return {
            "available": account.available_points,
            "reserved": account.reserved_points,
            "buckets": bucket_outs,
            "next_expiry": next_expiry,
            "daily_grant_amount": cfg.points_amount or INITIAL_DAILY_GRANT_POINTS,
            "grant_config_version": cfg.version,
            "business_date": shanghai_business_date(now).isoformat(),
            "timezone": "Asia/Shanghai",
        }

    async def get_current_subscription(self) -> dict:
        """Return beta entitlement + point projection for the current user.

        Legacy monthly-token fields remain under ``legacy_monthly_token`` for
        internal callers; UI must not treat them as purchase/upgrade truth.
        """
        result = await self.db.execute(
            select(User).where(User.id == self.user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise SubscriptionError("用户不存在")

        entitlement = get_beta_entitlement(is_admin=bool(getattr(user, "is_admin", False)))
        legacy = self._legacy_monthly_token_status(user)
        points = await self._point_projection()

        return {
            **entitlement.to_dict(),
            **points,
            "can_start_interview": points["available"] > 0,
            "legacy_monthly_token": legacy,
        }

    async def pre_check(self) -> dict:
        """Pre-check before starting an interview: legacy monthly-token comparison."""
        result = await self.db.execute(
            select(User).where(User.id == self.user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise SubscriptionError("用户不存在")

        legacy = self._legacy_monthly_token_status(user)
        if legacy["monthly_token_remaining"] <= 0:
            raise SubscriptionError(
                "本月 token 配额已用尽。请升级方案或等待下月重置。",
                "QUOTA_EXHAUSTED",
            )

        estimated_cost = 28000  # Rough estimate per interview
        remaining_after = legacy["monthly_token_remaining"] - estimated_cost
        return {
            "can_proceed": True,
            "estimated_token_cost": estimated_cost,
            "monthly_token_remaining_before": legacy["monthly_token_remaining"],
            "monthly_token_remaining_after": max(remaining_after, 0),
        }

    async def reset_monthly_quota(self) -> dict:
        """Monthly cron: reset all users' monthly_token_used to 0."""
        stmt = update(User).values(
            monthly_token_used=0, quota_reset_at=datetime.now(timezone.utc)
        )
        result = await self.db.execute(stmt)
        return {"reset_count": result.rowcount}  # type: ignore[attr-defined]
