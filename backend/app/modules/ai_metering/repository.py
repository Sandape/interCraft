"""REQ-061 AI Metering persistence helpers (T019).

Account/bucket projections update in the same transaction as append-only
ledger events and zero-sum postings.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_rls_user_id
from app.core.ids import new_uuid_v7
from app.modules.ai_metering.models import (
    PointAccount,
    PointBucket,
    PointLedgerEvent,
    PointLedgerPosting,
    PointQuote,
    PointReservation,
)


def ledger_subject_id(user_id: UUID) -> str:
    """Stable pseudonymous ledger subject (no cascade delete with user row)."""
    digest = hashlib.sha256(f"ai-ledger:{user_id}".encode()).hexdigest()[:32]
    return f"s_{digest}"


class PointMeteringRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bind_tenant(self, user_id: UUID) -> None:
        """Bind FORCE RLS identity for tenant-scoped metering tables.

        Required after every ``commit`` (SET LOCAL resets) and for workers /
        tests that open sessions without ``db_session_user_dep``.
        """
        await set_rls_user_id(self.session, user_id)

    async def get_account(self, user_id: UUID) -> PointAccount | None:
        await self.bind_tenant(user_id)
        result = await self.session.execute(
            select(PointAccount).where(PointAccount.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_account(self, user_id: UUID) -> PointAccount:
        await self.bind_tenant(user_id)
        account = await self.get_account(user_id)
        if account is not None:
            return account
        from sqlalchemy.exc import IntegrityError

        try:
            async with self.session.begin_nested():
                account = PointAccount(
                    user_id=user_id,
                    subject_id=ledger_subject_id(user_id),
                    available_points=0,
                    reserved_points=0,
                    projection_sequence=0,
                    status="active",
                )
                self.session.add(account)
                await self.session.flush()
                return account
        except IntegrityError:
            account = await self.get_account(user_id)
            if account is None:
                raise
            return account

    async def list_active_buckets_fifo(self, user_id: UUID) -> list[PointBucket]:
        await self.bind_tenant(user_id)
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(PointBucket)
            .where(
                PointBucket.user_id == user_id,
                PointBucket.status == "active",
                PointBucket.expires_at > now,
                PointBucket.available_points > 0,
            )
            .order_by(PointBucket.expires_at.asc(), PointBucket.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_buckets_for_user(self, user_id: UUID) -> list[PointBucket]:
        await self.bind_tenant(user_id)
        result = await self.session.execute(
            select(PointBucket)
            .where(PointBucket.user_id == user_id)
            .order_by(PointBucket.expires_at.asc(), PointBucket.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_bucket(self, bucket_id: UUID) -> PointBucket | None:
        result = await self.session.execute(
            select(PointBucket).where(PointBucket.id == bucket_id)
        )
        return result.scalar_one_or_none()

    async def find_event_by_idempotency(
        self, idempotency_key: str
    ) -> PointLedgerEvent | None:
        result = await self.session.execute(
            select(PointLedgerEvent).where(
                PointLedgerEvent.idempotency_key == idempotency_key
            )
        )
        return result.scalar_one_or_none()

    async def get_reservation(self, reservation_id: UUID) -> PointReservation | None:
        result = await self.session.execute(
            select(PointReservation).where(PointReservation.id == reservation_id)
        )
        return result.scalar_one_or_none()

    async def get_quote(self, quote_id: UUID) -> PointQuote | None:
        result = await self.session.execute(
            select(PointQuote).where(PointQuote.id == quote_id)
        )
        return result.scalar_one_or_none()

    async def append_event_with_postings(
        self,
        *,
        account: PointAccount,
        event_type: str,
        idempotency_key: str,
        available_delta: int,
        reserved_delta: int,
        business_date: date,
        postings: Sequence[tuple[str, int, UUID | None]],
        bucket_id: UUID | None = None,
        reservation_id: UUID | None = None,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        milestone_id: UUID | None = None,
        source_event_id: UUID | None = None,
        corrects_event_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
        config_version_id: UUID | None = None,
        price_version_id: UUID | None = None,
        correlation_id: str | None = None,
        expiry_at: datetime | None = None,
        payload: dict[str, Any] | None = None,
    ) -> PointLedgerEvent:
        """Append one ledger event, zero-sum postings, and bump account projection.

        ``postings`` is a sequence of ``(compartment, quantity, bucket_id)``.
        Quantities across compartments for one event must sum to zero.
        """
        total = sum(qty for _, qty, _ in postings)
        if total != 0:
            raise ValueError(f"postings must conserve value (sum={total})")

        before_available = account.available_points
        before_reserved = account.reserved_points
        after_available = before_available + available_delta
        after_reserved = before_reserved + reserved_delta
        if after_available < 0 or after_reserved < 0:
            raise ValueError("negative balance forbidden")

        account.projection_sequence += 1
        account.available_points = after_available
        account.reserved_points = after_reserved
        account.updated_at = datetime.now(timezone.utc)

        event = PointLedgerEvent(
            id=new_uuid_v7(),
            idempotency_key=idempotency_key,
            event_type=event_type,
            event_version=1,
            user_id=account.user_id,
            subject_id=account.subject_id,
            account_user_id=account.user_id,
            bucket_id=bucket_id,
            reservation_id=reservation_id,
            task_id=task_id,
            execution_id=execution_id,
            milestone_id=milestone_id,
            available_delta=available_delta,
            reserved_delta=reserved_delta,
            business_date=business_date,
            expiry_at=expiry_at,
            source_event_id=source_event_id,
            corrects_event_id=corrects_event_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            config_version_id=config_version_id,
            price_version_id=price_version_id,
            correlation_id=correlation_id,
            account_sequence=account.projection_sequence,
            before_available=before_available,
            after_available=after_available,
            before_reserved=before_reserved,
            after_reserved=after_reserved,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()

        for sequence, (compartment, quantity, posting_bucket_id) in enumerate(
            postings, start=1
        ):
            self.session.add(
                PointLedgerPosting(
                    id=new_uuid_v7(),
                    event_id=event.id,
                    subject_id=account.subject_id,
                    compartment=compartment,
                    quantity=quantity,
                    bucket_id=posting_bucket_id,
                    task_id=task_id,
                    execution_id=execution_id,
                    milestone_id=milestone_id,
                    sequence=sequence,
                )
            )
        await self.session.flush()
        return event


__all__ = [
    "PointMeteringRepository",
    "ledger_subject_id",
]
