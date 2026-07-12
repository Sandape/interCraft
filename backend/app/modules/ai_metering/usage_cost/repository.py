"""REQ-061 usage/cost persistence (T020)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_metering.usage_cost.models import (
    CostAdjustment,
    CostAllocation,
    CostRateVersion,
    FxRateVersion,
    UsageCostEvent,
)


class UsageCostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_idempotency(self, idempotency_key: str) -> UsageCostEvent | None:
        result = await self.session.execute(
            select(UsageCostEvent).where(
                UsageCostEvent.idempotency_key == idempotency_key
            )
        )
        return result.scalar_one_or_none()

    async def get_event(self, event_id: UUID) -> UsageCostEvent | None:
        result = await self.session.execute(
            select(UsageCostEvent).where(UsageCostEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_active_rates(
        self,
        *,
        provider_internal_key: str,
        model_or_tool_key: str,
        as_of: datetime,
    ) -> list[CostRateVersion]:
        result = await self.session.execute(
            select(CostRateVersion)
            .where(
                CostRateVersion.provider_internal_key == provider_internal_key,
                CostRateVersion.model_or_tool_key == model_or_tool_key,
                CostRateVersion.status == "active",
                CostRateVersion.effective_from <= as_of,
            )
            .order_by(CostRateVersion.effective_from.desc())
        )
        rows = list(result.scalars().all())
        return [
            r
            for r in rows
            if r.effective_to is None or r.effective_to > as_of
        ]

    async def list_active_fx(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        as_of: datetime,
    ) -> list[FxRateVersion]:
        result = await self.session.execute(
            select(FxRateVersion)
            .where(
                FxRateVersion.base_currency == base_currency,
                FxRateVersion.quote_currency == quote_currency,
                FxRateVersion.status == "active",
                FxRateVersion.effective_from <= as_of,
            )
            .order_by(FxRateVersion.effective_from.desc())
        )
        rows = list(result.scalars().all())
        return [
            r
            for r in rows
            if r.effective_to is None or r.effective_to > as_of
        ]

    async def insert_usage_cost_event(self, event: UsageCostEvent) -> UsageCostEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def insert_adjustment(self, adjustment: CostAdjustment) -> CostAdjustment:
        self.session.add(adjustment)
        await self.session.flush()
        return adjustment

    async def insert_allocations(
        self, allocations: Sequence[CostAllocation]
    ) -> list[CostAllocation]:
        for row in allocations:
            self.session.add(row)
        await self.session.flush()
        return list(allocations)

    async def sum_allocations(self, source_event_id: UUID) -> Decimal:
        result = await self.session.execute(
            select(CostAllocation).where(
                CostAllocation.source_event_id == source_event_id
            )
        )
        rows = list(result.scalars().all())
        return sum((r.allocated_original for r in rows), Decimal("0"))


__all__ = ["UsageCostRepository"]
