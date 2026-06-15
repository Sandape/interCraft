"""Phase 6 — Subscription service: plans, quota, pre-check, monthly reset."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.content.models import SubscriptionPlan


class SubscriptionError(Exception):
    pass


class SubscriptionService:
    """Subscription plan info, quota checks, pre-check for interview start."""

    def __init__(self, db: AsyncSession, user_id: UUID | None = None) -> None:
        self.db = db
        self.user_id = user_id

    async def list_plans(self) -> list[SubscriptionPlan]:
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def get_current_subscription(self) -> dict:
        """Return current user's subscription status with usage."""
        result = await self.db.execute(
            select(User).where(User.id == self.user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise SubscriptionError("用户不存在")

        remaining = user.monthly_token_quota - user.monthly_token_used
        usage_pct = round((user.monthly_token_used / max(user.monthly_token_quota, 1)) * 100, 1)

        # Next reset date = first day of next month
        now = datetime.now(timezone.utc)
        if now.month == 12:
            reset_date = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            reset_date = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

        return {
            "plan": user.subscription,
            "monthly_token_quota": user.monthly_token_quota,
            "monthly_token_used": user.monthly_token_used,
            "monthly_token_remaining": max(remaining, 0),
            "usage_pct": usage_pct,
            "reset_date": reset_date,
            "can_start_interview": remaining > 0,
        }

    async def pre_check(self) -> dict:
        """Pre-check before starting an interview: verify quota."""
        sub = await self.get_current_subscription()
        if sub["monthly_token_remaining"] <= 0:
            raise SubscriptionError(
                "本月 token 配额已用尽。请升级方案或等待下月重置。",
                "QUOTA_EXHAUSTED",
            )

        estimated_cost = 28000  # Rough estimate per interview
        remaining_after = sub["monthly_token_remaining"] - estimated_cost
        return {
            "can_proceed": True,
            "estimated_token_cost": estimated_cost,
            "monthly_token_remaining_before": sub["monthly_token_remaining"],
            "monthly_token_remaining_after": max(remaining_after, 0),
        }

    async def reset_monthly_quota(self) -> dict:
        """Monthly cron: reset all users' monthly_token_used to 0."""
        stmt = update(User).values(monthly_token_used=0, quota_reset_at=datetime.now(timezone.utc))
        result = await self.db.execute(stmt)
        return {"reset_count": result.rowcount}  # type: ignore[attr-defined]
