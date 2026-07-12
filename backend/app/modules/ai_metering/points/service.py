"""REQ-061 semantic point commands (T019).

Callers issue grant/reserve/settle/release/refund/compensate/reverse.
Direct posting creation stays private to the metering repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_metering.models import (
    PointAccount,
    PointBucket,
    PointLedgerEvent,
    PointQuote,
    PointReservation,
)
from app.modules.ai_metering.points.ledger import LedgerError
from app.modules.ai_metering.repository import PointMeteringRepository, ledger_subject_id

SHANGHAI = ZoneInfo("Asia/Shanghai")


def shanghai_business_date(at: datetime | None = None) -> date:
    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(SHANGHAI).date()


@dataclass(frozen=True, slots=True)
class PointCommandResult:
    event: PointLedgerEvent
    account: PointAccount
    reservation: PointReservation | None = None
    bucket: PointBucket | None = None
    reused: bool = False


class PointMeteringService:
    """Atomic semantic ledger commands with FIFO buckets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PointMeteringRepository(session)

    async def ensure_daily_entitlement(
        self,
        *,
        user_id: UUID,
        is_new_user: bool = True,
        at: datetime | None = None,
    ) -> PointCommandResult:
        """Idempotent Shanghai-day grant so acceptance never starts at zero balance."""
        from app.modules.ai_metering.models import DailyGrantConfigVersion
        from app.modules.ai_metering.points.catalog import INITIAL_DAILY_GRANT_POINTS
        from app.modules.ai_metering.points.configuration import (
            DEFAULT_TIMEZONE,
            plan_daily_grant,
            resolve_effective_grant_config,
            shanghai_business_date,
        )

        moment = at or datetime.now(timezone.utc)
        biz = shanghai_business_date(moment)
        plan = plan_daily_grant(
            user_id=user_id,
            business_date=biz,
            at=moment,
            is_new_user=is_new_user,
        )
        cfg = resolve_effective_grant_config(at=moment)
        await self.repo.bind_tenant(user_id)
        result = await self.session.execute(
            select(DailyGrantConfigVersion).where(
                DailyGrantConfigVersion.version == cfg.version
            )
        )
        config_row = result.scalar_one_or_none()
        if config_row is None:
            config_row = DailyGrantConfigVersion(
                id=new_uuid_v7(),
                version=cfg.version,
                points_amount=cfg.points_amount or INITIAL_DAILY_GRANT_POINTS,
                timezone=cfg.timezone or DEFAULT_TIMEZONE,
                effective_at=cfg.effective_at,
                status="active",
                reason=cfg.reason or "daily grant bootstrap",
            )
            self.session.add(config_row)
            await self.session.flush()

        return await self.grant(
            user_id=user_id,
            points=plan.points,
            idempotency_key=plan.idempotency_key,
            expires_at=plan.expires_at,
            business_date=plan.business_date,
            grant_config_version_id=config_row.id,
            reason=(
                "new_user_immediate_grant" if is_new_user else "shanghai_midnight_grant"
            ),
        )

    async def grant(
        self,
        *,
        user_id: UUID,
        points: int,
        idempotency_key: str,
        expires_at: datetime,
        business_date: date | None = None,
        grant_config_version_id: UUID | None = None,
        bucket_type: str = "daily_experience",
        event_type: str = "grant",
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
        source_event_id: UUID | None = None,
    ) -> PointCommandResult:
        if points <= 0:
            raise LedgerError("grant points must be positive")
        await self.repo.bind_tenant(user_id)
        existing = await self.repo.find_event_by_idempotency(idempotency_key)
        if existing is not None:
            account = await self.repo.get_or_create_account(user_id)
            return PointCommandResult(event=existing, account=account, reused=True)

        account = await self.repo.get_or_create_account(user_id)
        biz = business_date or shanghai_business_date()
        from sqlalchemy.exc import IntegrityError

        try:
            async with self.session.begin_nested():
                bucket = PointBucket(
                    id=new_uuid_v7(),
                    user_id=user_id,
                    subject_id=account.subject_id,
                    bucket_type=bucket_type,
                    business_date=biz,
                    grant_config_version_id=grant_config_version_id,
                    granted_points=points,
                    available_points=points,
                    reserved_points=0,
                    consumed_points=0,
                    expired_points=0,
                    expires_at=expires_at,
                    status="active",
                )
                self.session.add(bucket)
                await self.session.flush()

                event = await self.repo.append_event_with_postings(
                    account=account,
                    event_type=event_type,
                    idempotency_key=idempotency_key,
                    available_delta=points,
                    reserved_delta=0,
                    business_date=biz,
                    bucket_id=bucket.id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    reason=reason,
                    config_version_id=grant_config_version_id,
                    expiry_at=expires_at,
                    source_event_id=source_event_id,
                    postings=[
                        ("platform_issuance", -points, bucket.id),
                        ("user_available", points, bucket.id),
                    ],
                )
                bucket.source_event_id = event.id
                await self.session.flush()
                return PointCommandResult(event=event, account=account, bucket=bucket)
        except IntegrityError:
            existing = await self.repo.find_event_by_idempotency(idempotency_key)
            if existing is None:
                raise
            account = await self.repo.get_or_create_account(user_id)
            return PointCommandResult(event=existing, account=account, reused=True)

    async def compensate(
        self,
        *,
        user_id: UUID,
        points: int,
        idempotency_key: str,
        expires_at: datetime,
        business_date: date | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
        source_event_id: UUID | None = None,
    ) -> PointCommandResult:
        return await self.grant(
            user_id=user_id,
            points=points,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
            business_date=business_date,
            bucket_type="compensation",
            event_type="compensate",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason or "compensation",
            source_event_id=source_event_id,
        )

    async def reserve(
        self,
        *,
        user_id: UUID,
        points: int,
        quote_id: UUID,
        idempotency_key: str,
        task_id: UUID | None = None,
        expires_at: datetime | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> PointCommandResult:
        if points <= 0:
            raise LedgerError("reserve points must be positive")
        await self.repo.bind_tenant(user_id)
        existing = await self.repo.find_event_by_idempotency(idempotency_key)
        if existing is not None:
            account = await self.repo.get_or_create_account(user_id)
            reservation = None
            if existing.reservation_id is not None:
                reservation = await self.repo.get_reservation(existing.reservation_id)
            return PointCommandResult(
                event=existing, account=account, reservation=reservation, reused=True
            )

        account = await self.repo.get_or_create_account(user_id)
        if account.available_points < points:
            raise LedgerError("insufficient balance")

        quote = await self.repo.get_quote(quote_id)
        if quote is None:
            raise LedgerError("quote not found")
        if quote.user_id != user_id:
            raise LedgerError("quote owner mismatch")

        buckets = await self.repo.list_active_buckets_fifo(user_id)
        remaining = points
        draws: list[tuple[PointBucket, int]] = []
        for bucket in buckets:
            if remaining <= 0:
                break
            take = min(bucket.available_points, remaining)
            if take <= 0:
                continue
            draws.append((bucket, take))
            remaining -= take
        if remaining > 0:
            raise LedgerError("insufficient balance")

        source_bucket_ids: list[str] = []
        for bucket, take in draws:
            bucket.available_points -= take
            bucket.reserved_points += take
            bucket.updated_at = datetime.now(timezone.utc)
            source_bucket_ids.append(str(bucket.id))

        reservation = PointReservation(
            id=new_uuid_v7(),
            user_id=user_id,
            subject_id=account.subject_id,
            task_id=task_id,
            quote_id=quote_id,
            reserved_points=points,
            remaining_points=points,
            source_bucket_ids=source_bucket_ids,
            status="reserved",
            expires_at=expires_at,
        )
        self.session.add(reservation)
        await self.session.flush()

        postings: list[tuple[str, int, UUID | None]] = []
        for bucket, take in draws:
            postings.append(("user_available", -take, bucket.id))
            postings.append(("user_reserved", take, bucket.id))

        event = await self.repo.append_event_with_postings(
            account=account,
            event_type="reserve",
            idempotency_key=idempotency_key,
            available_delta=-points,
            reserved_delta=points,
            business_date=shanghai_business_date(),
            reservation_id=reservation.id,
            task_id=task_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            price_version_id=quote.price_table_version_id,
            postings=postings,
            payload={"source_bucket_ids": source_bucket_ids},
        )
        quote.status = "reserved"
        await self.session.flush()
        return PointCommandResult(
            event=event, account=account, reservation=reservation
        )

    async def settle(
        self,
        *,
        user_id: UUID,
        points: int,
        reservation_id: UUID,
        idempotency_key: str,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        milestone_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> PointCommandResult:
        return await self._consume_reservation(
            user_id=user_id,
            points=points,
            reservation_id=reservation_id,
            idempotency_key=idempotency_key,
            event_type="settle",
            task_id=task_id,
            execution_id=execution_id,
            milestone_id=milestone_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            restore_available=False,
        )

    async def release(
        self,
        *,
        user_id: UUID,
        points: int,
        reservation_id: UUID,
        idempotency_key: str,
        task_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> PointCommandResult:
        return await self._consume_reservation(
            user_id=user_id,
            points=points,
            reservation_id=reservation_id,
            idempotency_key=idempotency_key,
            event_type="release",
            task_id=task_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            restore_available=True,
        )

    async def refund(
        self,
        *,
        user_id: UUID,
        points: int,
        idempotency_key: str,
        source_event_id: UUID | None = None,
        task_id: UUID | None = None,
        bucket_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
        expires_at: datetime | None = None,
    ) -> PointCommandResult:
        if points <= 0:
            raise LedgerError("refund points must be positive")
        await self.repo.bind_tenant(user_id)
        existing = await self.repo.find_event_by_idempotency(idempotency_key)
        if existing is not None:
            account = await self.repo.get_or_create_account(user_id)
            return PointCommandResult(event=existing, account=account, reused=True)

        account = await self.repo.get_or_create_account(user_id)
        target = None
        if bucket_id is not None:
            target = await self.repo.get_bucket(bucket_id)
        if target is None:
            buckets = await self.repo.list_buckets_for_user(user_id)
            active = [
                b
                for b in buckets
                if b.status == "active" and b.expires_at > datetime.now(timezone.utc)
            ]
            target = active[0] if active else None

        if target is None or target.expires_at <= datetime.now(timezone.utc):
            # Expired bucket → linked compensation grant (24h default).
            comp_expires = expires_at or (
                datetime.now(timezone.utc).replace(microsecond=0)
            )
            # Default 24h compensation window from now if not provided.
            if expires_at is None:
                from datetime import timedelta

                comp_expires = datetime.now(timezone.utc) + timedelta(hours=24)
            return await self.compensate(
                user_id=user_id,
                points=points,
                idempotency_key=idempotency_key,
                expires_at=comp_expires,
                actor_type=actor_type,
                actor_id=actor_id,
                reason=reason or "refund_expired_compensation",
                source_event_id=source_event_id,
            )

        target.available_points += points
        target.consumed_points = max(0, target.consumed_points - points)
        target.updated_at = datetime.now(timezone.utc)
        event = await self.repo.append_event_with_postings(
            account=account,
            event_type="refund",
            idempotency_key=idempotency_key,
            available_delta=points,
            reserved_delta=0,
            business_date=shanghai_business_date(),
            bucket_id=target.id,
            task_id=task_id,
            source_event_id=source_event_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            postings=[
                ("consumed", -points, target.id),
                ("user_available", points, target.id),
            ],
        )
        return PointCommandResult(event=event, account=account, bucket=target)

    async def reverse(
        self,
        *,
        user_id: UUID,
        points: int,
        source_event_id: UUID,
        idempotency_key: str,
        task_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> PointCommandResult:
        """Create a correcting reverse that restores available points."""
        return await self.refund(
            user_id=user_id,
            points=points,
            idempotency_key=idempotency_key,
            source_event_id=source_event_id,
            task_id=task_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason or "reverse",
        )

    async def expire(
        self,
        *,
        user_id: UUID,
        bucket_id: UUID,
        idempotency_key: str,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> PointCommandResult:
        """Expire unreserved available points on a bucket (reserved quantities stay)."""
        await self.repo.bind_tenant(user_id)
        existing = await self.repo.find_event_by_idempotency(idempotency_key)
        if existing is not None:
            account = await self.repo.get_or_create_account(user_id)
            bucket = await self.repo.get_bucket(bucket_id)
            return PointCommandResult(
                event=existing, account=account, bucket=bucket, reused=True
            )

        account = await self.repo.get_or_create_account(user_id)
        bucket = await self.repo.get_bucket(bucket_id)
        if bucket is None or bucket.user_id != user_id:
            raise LedgerError("bucket not found")
        points = bucket.available_points
        if points <= 0:
            raise LedgerError("nothing to expire")

        bucket.available_points = 0
        bucket.expired_points += points
        bucket.status = "expired"
        bucket.updated_at = datetime.now(timezone.utc)

        event = await self.repo.append_event_with_postings(
            account=account,
            event_type="expire",
            idempotency_key=idempotency_key,
            available_delta=-points,
            reserved_delta=0,
            business_date=shanghai_business_date(),
            bucket_id=bucket.id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason or "bucket_expiry",
            postings=[
                ("user_available", -points, bucket.id),
                ("expired", points, bucket.id),
            ],
        )
        return PointCommandResult(event=event, account=account, bucket=bucket)

    async def _consume_reservation(
        self,
        *,
        user_id: UUID,
        points: int,
        reservation_id: UUID,
        idempotency_key: str,
        event_type: str,
        restore_available: bool,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        milestone_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> PointCommandResult:
        if points <= 0:
            raise LedgerError(f"{event_type} points must be positive")
        await self.repo.bind_tenant(user_id)
        existing = await self.repo.find_event_by_idempotency(idempotency_key)
        if existing is not None:
            account = await self.repo.get_or_create_account(user_id)
            reservation = await self.repo.get_reservation(reservation_id)
            return PointCommandResult(
                event=existing, account=account, reservation=reservation, reused=True
            )

        account = await self.repo.get_or_create_account(user_id)
        reservation = await self.repo.get_reservation(reservation_id)
        if reservation is None or reservation.user_id != user_id:
            raise LedgerError("reservation not found")
        if points > reservation.remaining_points:
            raise LedgerError(f"{event_type} exceeds reservation")
        if account.reserved_points < points:
            raise LedgerError("reserved projection insufficient")

        # Draw against source buckets in recorded order.
        remaining = points
        draws: list[tuple[PointBucket, int]] = []
        for raw_id in reservation.source_bucket_ids:
            if remaining <= 0:
                break
            bucket = await self.repo.get_bucket(UUID(str(raw_id)))
            if bucket is None:
                continue
            take = min(bucket.reserved_points, remaining)
            if take <= 0:
                continue
            draws.append((bucket, take))
            remaining -= take
        if remaining > 0:
            raise LedgerError("reservation bucket allocation insufficient")

        for bucket, take in draws:
            bucket.reserved_points -= take
            if restore_available:
                bucket.available_points += take
            else:
                bucket.consumed_points += take
            bucket.updated_at = datetime.now(timezone.utc)

        reservation.remaining_points -= points
        if reservation.remaining_points == 0:
            reservation.status = "released" if restore_available else "settled"
        elif not restore_available:
            reservation.status = "partially_settled"
        reservation.updated_at = datetime.now(timezone.utc)

        postings: list[tuple[str, int, UUID | None]] = []
        for bucket, take in draws:
            postings.append(("user_reserved", -take, bucket.id))
            if restore_available:
                postings.append(("user_available", take, bucket.id))
            else:
                postings.append(("consumed", take, bucket.id))

        available_delta = points if restore_available else 0
        event = await self.repo.append_event_with_postings(
            account=account,
            event_type=event_type,
            idempotency_key=idempotency_key,
            available_delta=available_delta,
            reserved_delta=-points,
            business_date=shanghai_business_date(),
            reservation_id=reservation.id,
            task_id=task_id or reservation.task_id,
            execution_id=execution_id,
            milestone_id=milestone_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            postings=postings,
        )
        return PointCommandResult(
            event=event, account=account, reservation=reservation
        )


__all__ = [
    "PointMeteringService",
    "PointCommandResult",
    "shanghai_business_date",
    "LedgerError",
    "ledger_subject_id",
]
