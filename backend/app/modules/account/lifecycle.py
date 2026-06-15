"""Phase 6 — Account lifecycle service (M20)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.account.notification import NotificationService


class LifecycleError(Exception):
    pass


class LifecycleService:
    """User account lifecycle: delete, cancel-deletion, status query, purge."""

    def __init__(self, db: AsyncSession, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id
        self.settings = get_settings()

    async def _get_user(self) -> User:
        result = await self.db.execute(
            select(User).where(User.id == self.user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise LifecycleError("用户不存在")
        return user

    async def delete_account(self) -> dict:
        """Initiate account deletion. Sets status=soft_deleted with 7d cancellation deadline and 90d purge."""
        user = await self._get_user()
        if user.status == "soft_deleted":
            raise LifecycleError("账号已在注销流程中", "ALREADY_SOFT_DELETED")

        now = datetime.now(timezone.utc)
        scheduled_purge_at = now + timedelta(days=self.settings.account_purge_days)
        cancellation_deadline = now + timedelta(days=self.settings.account_deletion_grace_days)

        stmt = (
            update(User)
            .where(User.id == self.user_id)
            .values(
                status="soft_deleted",
                scheduled_purge_at=scheduled_purge_at,
                cancellation_deadline=cancellation_deadline,
            )
        )
        await self.db.execute(stmt)

        notif = NotificationService(self.db, self.user_id)
        await notif.create(
            type_="account_deletion_initiated",
            title="账号注销已发起",
            message=f"您的账号已进入注销流程。{self.settings.account_deletion_grace_days} 天内可取消，{self.settings.account_purge_days} 天后将物理清除。",
        )

        return {
            "status": "soft_deleted",
            "scheduled_purge_at": scheduled_purge_at,
            "cancellation_deadline": cancellation_deadline,
        }

    async def cancel_deletion(self) -> dict:
        """Cancel account deletion before the cancellation deadline."""
        user = await self._get_user()
        if user.status != "soft_deleted":
            raise LifecycleError("账号当前不在注销流程中", "NOT_IN_DELETION")

        now = datetime.now(timezone.utc)
        if user.cancellation_deadline and now > user.cancellation_deadline:
            raise LifecycleError("冷静期已过，无法取消注销", "CANCELLATION_DEADLINE_PASSED")

        stmt = (
            update(User)
            .where(User.id == self.user_id)
            .values(
                status="active",
                scheduled_purge_at=None,
                cancellation_deadline=None,
            )
        )
        await self.db.execute(stmt)

        notif = NotificationService(self.db, self.user_id)
        await notif.create(
            type_="account_deletion_cancelled",
            title="账号注销已取消",
            message="您的账号已恢复正常。",
        )

        return {"status": "active"}

    async def get_deletion_status(self) -> dict:
        """Return detailed deletion status."""
        user = await self._get_user()
        now = datetime.now(timezone.utc)

        if user.status == "soft_deleted":
            days_until_purge = (user.scheduled_purge_at - now).days if user.scheduled_purge_at else None
            days_until_cancel = (user.cancellation_deadline - now).days if user.cancellation_deadline else None
            can_cancel = days_until_cancel is not None and days_until_cancel > 0 if days_until_cancel is not None else False
            return {
                "status": "soft_deleted",
                "is_deleting": True,
                "scheduled_purge_at": user.scheduled_purge_at,
                "cancellation_deadline": user.cancellation_deadline,
                "can_cancel": bool(can_cancel),
                "days_until_purge": days_until_purge,
                "days_until_cancellation_deadline": days_until_cancel,
            }
        elif user.status == "purged":
            return {
                "status": "purged",
                "is_deleting": True,
                "message": "账号数据正在清除中。",
            }
        else:
            return {
                "status": user.status,
                "is_deleting": False,
            }

    async def purge_expired_accounts(self) -> dict:
        """Daily cron: mark soft_deleted accounts past scheduled_purge_at as purged."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(User)
            .where(User.status == "soft_deleted")
            .where(User.scheduled_purge_at <= now)
            .values(status="purged")
        )
        result = await self.db.execute(stmt)
        purged_count = result.rowcount  # type: ignore[attr-defined]
        return {"purged_count": purged_count}

    async def physical_cleanup(self, batch_size: int = 100) -> dict:
        """Weekly cron: physically delete purged users older than 7 days, in batches."""
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        # Select batch of purged users
        result = await self.db.execute(
            select(User).where(User.status == "purged", User.updated_at <= seven_days_ago).limit(batch_size)
        )
        users = result.scalars().all()

        deleted_count = 0
        for user in users:
            await self.db.delete(user)
            deleted_count += 1

        return {"deleted_count": deleted_count}
