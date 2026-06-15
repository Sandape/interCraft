"""AbilityService — business logic for ability dimensions (US5)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException

from app.modules.abilities.repository import AbilityDimensionRepository
from app.modules.abilities.schemas import ALLOWED_DIMENSION_KEYS, ALLOWED_SUB_KEYS


class AbilityService:
    def __init__(self, repo: AbilityDimensionRepository) -> None:
        self.repo = repo

    async def read(self, user_id: UUID, *, is_active: bool | None = None) -> list:
        return await self.repo.list_for_user(user_id, is_active=is_active)

    async def get_by_key(self, user_id: UUID, dimension_key: str) -> dict:
        _validate_dimension_key(dimension_key)
        instance = await self.repo.get_by_key(user_id, dimension_key)
        if instance is None:
            raise HTTPException(status_code=404, detail="Dimension not found")
        return instance

    async def patch(self, user_id: UUID, dimension_key: str, patch_data: dict) -> dict:
        _validate_dimension_key(dimension_key)
        # Validate sub_scores keys
        sub_scores = patch_data.get("sub_scores")
        if sub_scores is not None:
            _validate_sub_keys(dimension_key, sub_scores)

        instance = await self.repo.patch(user_id, dimension_key, patch_data)
        if instance is None:
            raise HTTPException(status_code=404, detail="Dimension not found")
        return instance

    async def toggle(self, user_id: UUID, dimension_key: str, is_active: bool) -> dict:
        _validate_dimension_key(dimension_key)
        instance = await self.repo.toggle(user_id, dimension_key, is_active)
        if instance is None:
            raise HTTPException(status_code=404, detail="Dimension not found")
        return instance

    async def history(
        self,
        user_id: UUID,
        *,
        dimension_key: str | None = None,
        aggregate: str = "month",
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
    ) -> list:
        if aggregate not in ("month", "day"):
            raise HTTPException(status_code=422, detail="aggregate must be 'month' or 'day'")
        if dimension_key:
            _validate_dimension_key(dimension_key)
        return await self.repo.list_history(
            user_id,
            dimension_key=dimension_key,
            aggregate=aggregate,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    async def seed_for_new_user(self, user_id: UUID) -> list:
        return await self.repo.seed_for_new_user(user_id)


def _validate_dimension_key(key: str) -> None:
    if key not in ALLOWED_DIMENSION_KEYS:
        raise HTTPException(status_code=422, detail=f"Invalid dimension_key: {key}")


def _validate_sub_keys(dimension_key: str, sub_scores: dict) -> None:
    allowed = ALLOWED_SUB_KEYS.get(dimension_key, set())
    for key in sub_scores:
        if key not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid sub_key '{key}' for dimension '{dimension_key}'. Allowed: {allowed}",
            )


__all__ = ["AbilityService"]
