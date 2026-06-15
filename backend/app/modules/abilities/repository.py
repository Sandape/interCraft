"""AbilityDimensionRepository — CRUD for ability_dimensions + history."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AbilityDimension as AbilityDimensionEnum
from app.modules.abilities.models import AbilityDimension, AbilityDimensionHistory


class AbilityDimensionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(
        self, user_id: UUID, *, is_active: bool | None = None
    ) -> list[AbilityDimension]:
        stmt = select(AbilityDimension).where(AbilityDimension.user_id == user_id)
        if is_active is not None:
            stmt = stmt.where(AbilityDimension.is_active == is_active)
        stmt = stmt.order_by(AbilityDimension.dimension_key.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_key(
        self, user_id: UUID, dimension_key: str
    ) -> AbilityDimension | None:
        stmt = select(AbilityDimension).where(
            AbilityDimension.user_id == user_id,
            AbilityDimension.dimension_key == dimension_key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def patch(
        self, user_id: UUID, dimension_key: str, patch_data: dict
    ) -> AbilityDimension | None:
        instance = await self.get_by_key(user_id, dimension_key)
        if instance is None:
            return None
        for k, v in patch_data.items():
            if hasattr(instance, k) and v is not None:
                setattr(instance, k, v)
        instance.last_updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def toggle(
        self, user_id: UUID, dimension_key: str, is_active: bool
    ) -> AbilityDimension | None:
        return await self.patch(user_id, dimension_key, {"is_active": is_active})

    async def seed_for_new_user(self, user_id: UUID) -> list[AbilityDimension]:
        dimensions: list[AbilityDimension] = []
        for dim_key in AbilityDimensionEnum:
            dim = AbilityDimension(
                user_id=user_id,
                dimension_key=dim_key.value,
                actual_score=Decimal("0.00"),
                ideal_score=Decimal("10.00"),
                sub_scores=_default_sub_scores(dim_key.value),
                is_active=True,
                source="manual",
            )
            self.session.add(dim)
            dimensions.append(dim)
        await self.session.flush()
        return dimensions

    # --- History ---

    async def list_history(
        self,
        user_id: UUID,
        *,
        dimension_key: str | None = None,
        aggregate: str = "month",
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
    ) -> list[AbilityDimensionHistory]:
        stmt = select(AbilityDimensionHistory).where(
            AbilityDimensionHistory.user_id == user_id,
            AbilityDimensionHistory.aggregate == aggregate,
        )
        if dimension_key:
            stmt = stmt.where(AbilityDimensionHistory.dimension_key == dimension_key)
        if from_date:
            stmt = stmt.where(AbilityDimensionHistory.snapshot_date >= from_date)
        if to_date:
            stmt = stmt.where(AbilityDimensionHistory.snapshot_date <= to_date)
        stmt = stmt.order_by(AbilityDimensionHistory.snapshot_date.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


def _default_sub_scores(dim_key: str) -> dict:
    from app.modules.abilities.schemas import ALLOWED_SUB_KEYS

    sub_keys = ALLOWED_SUB_KEYS.get(dim_key, set())
    return {k: {"actual": 0, "ideal": 10} for k in sub_keys}


__all__ = ["AbilityDimensionRepository"]
