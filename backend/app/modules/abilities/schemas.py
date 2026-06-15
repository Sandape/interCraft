"""Ability dimension Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ALLOWED_DIMENSION_KEYS = {
    "tech_depth", "architecture", "engineering_practice",
    "communication", "algorithm", "business",
}

ALLOWED_SUB_KEYS: dict[str, set[str]] = {
    "tech_depth": {"fundamentals", "system_design", "depth_specialty"},
    "architecture": {"decomposition", "tradeoffs", "scalability"},
    "engineering_practice": {"code_quality", "testing", "observability"},
    "communication": {"clarity", "structure", "conciseness"},
    "algorithm": {"data_structures", "complexity", "edge_cases"},
    "business": {"domain_knowledge", "product_sense", "user_empathy"},
}


class SubScore(BaseModel):
    actual: Decimal = Field(default=Decimal("0.00"), ge=0, le=10)
    ideal: Decimal = Field(default=Decimal("10.00"), ge=0, le=10)


class AbilityDimensionOut(BaseModel):
    id: UUID
    dimension_key: str
    actual_score: Decimal
    ideal_score: Decimal
    sub_scores: dict[str, Any]
    is_active: bool
    source: str
    last_updated_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AbilityDimensionListOut(BaseModel):
    data: list[AbilityDimensionOut]


class PatchAbilityDimensionInput(BaseModel):
    actual_score: Decimal | None = Field(default=None, ge=0, le=10)
    ideal_score: Decimal | None = Field(default=None, ge=0, le=10)
    sub_scores: dict[str, dict[str, Any]] | None = None
    is_active: bool | None = None

    @field_validator("actual_score", "ideal_score")
    @classmethod
    def score_range(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and (v < 0 or v > 10):
            raise ValueError("Score must be between 0 and 10")
        return v


class ToggleDimensionInput(BaseModel):
    is_active: bool = True


class AbilityHistoryPointOut(BaseModel):
    snapshot_date: str
    aggregate: str
    actual_score: Decimal
    ideal_score: Decimal
    dimension_key: str

    model_config = {"from_attributes": True}


class AbilityHistoryListOut(BaseModel):
    data: list[AbilityHistoryPointOut]


class DimensionMetaSubKey(BaseModel):
    key: str
    label_zh: str


class DimensionMeta(BaseModel):
    key: str
    label_zh: str
    label_en: str
    sub_keys: list[DimensionMetaSubKey]


class DimensionsMetaOut(BaseModel):
    dimensions: list[DimensionMeta]


__all__ = [
    "AbilityDimensionListOut",
    "AbilityDimensionOut",
    "AbilityHistoryListOut",
    "AbilityHistoryPointOut",
    "DimensionMeta",
    "DimensionMetaSubKey",
    "DimensionsMetaOut",
    "PatchAbilityDimensionInput",
    "SubScore",
    "ToggleDimensionInput",
]
