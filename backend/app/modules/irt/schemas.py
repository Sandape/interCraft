"""Pydantic schemas for the IRT module.

Per specs/030-irt-adaptive-diagnosis/plan.md §"Data Model" and §"API Contracts".

The schemas are intentionally narrow — the engine math returns a dataclass
(`ThetaResult`) and the repository returns ORM rows. Pydantic is used only
at the public boundary (CLI, API, integration) for validation + serialization.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Status values mirror the CHECK constraint on `irt_items.status` and are
# duplicated here as Literal types so Pydantic rejects invalid values at
# construction time.
ItemStatus = Literal["uncalibrated", "calibrated", "retired", "flagged"]
ItemModel = Literal["2pl", "3pl"]
ResponseLabel = Literal["correct", "incorrect"]

# Hard bounds mirror the DB CHECK constraints. Used in Pydantic validators
# so invalid values are rejected before the DB ever sees them.
_A_MIN: float = 0.0
_A_MAX: float = 5.0
_B_MIN: float = -6.0
_B_MAX: float = 6.0
_THETA_MIN: float = -6.0
_THETA_MAX: float = 6.0


class ItemCreate(BaseModel):
    """Input for seeding or inserting an item into the bank.

    `status` defaults to "uncalibrated" for new items; promotion to
    "calibrated" happens after offline calibration (US3) — not in US1.
    """

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(..., min_length=1, max_length=64)
    question_text_hash: str = Field(..., min_length=1, max_length=128)
    difficulty_b: float = Field(..., ge=_B_MIN, le=_B_MAX)
    discrimination_a: float = Field(..., ge=_A_MIN, le=_A_MAX)
    model: ItemModel = "2pl"
    status: ItemStatus = "uncalibrated"


class ItemOut(BaseModel):
    """Public representation of an item in the bank."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dimension: str
    difficulty_b: float
    discrimination_a: float
    model: ItemModel
    status: ItemStatus
    response_count: int
    standard_error: float
    last_calibrated_at: datetime | None = None


class ItemResponseIn(BaseModel):
    """Input for recording a user response to an item.

    `score` is preserved at full LLM resolution (0-10) for future 3-PL
    partial-credit work; US1 only branches on `response`.
    """

    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    response: ResponseLabel
    score: float = Field(..., ge=0.0, le=10.0)
    source_interview_id: UUID | None = None


class ThetaEstimate(BaseModel):
    """Per-dimension θ estimate output (consumed by aggregate_scores graph)."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    theta: float = Field(..., ge=_THETA_MIN, le=_THETA_MAX)
    standard_error: float = Field(..., gt=0.0)
    n_items: int = Field(..., ge=0)
    converged: bool


class ThetaResultSchema(BaseModel):
    """Output of `estimate_theta_mle` after Pydantic validation.

    Distinct from `ThetaEstimate` (which is the multi-dimension
    ability-profile output). `ThetaResultSchema` wraps the engine's
    raw result for use at the API/CLI boundary.
    """

    model_config = ConfigDict(extra="forbid")

    theta: float = Field(..., ge=_THETA_MIN, le=_THETA_MAX)
    standard_error: float = Field(..., gt=0.0)
    n_items: int = Field(..., ge=0)
    converged: bool
    iterations: int = Field(..., ge=0)


__all__ = [
    "ItemCreate",
    "ItemModel",
    "ItemOut",
    "ItemResponseIn",
    "ItemStatus",
    "ResponseLabel",
    "ThetaEstimate",
    "ThetaResultSchema",
]
