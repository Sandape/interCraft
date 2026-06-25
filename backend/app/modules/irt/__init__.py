"""irt — Item Response Theory library for ability diagnosis (REQ-030 US1).

Self-contained module (Constitution I: Library-First) implementing the
2-parameter logistic (2-PL) IRT model and Newton-Raphson marginal MLE for
per-dimension user ability θ (theta) estimation.

US1 scope: pure math (engine.py), Pydantic schemas, SQLAlchemy models, and
repository for `irt_items` / `irt_item_responses` / `irt_ability_thetas`
tables. 3-PL guessing, offline calibration batch (US3), and adaptive
question selection (US2/US4) are deferred — see `specs/030-irt-adaptive-diagnosis/tasks.md`.

See README.md for math formulation, 2-PL vs 3-PL rationale, and CLI usage.
"""
from __future__ import annotations

from app.modules.irt.engine import (
    ThetaResult,
    estimate_theta_mle,
    gradient,
    hessian,
    log_likelihood,
    probability_2pl,
)
from app.modules.irt.models import AbilityTheta, Item, ItemResponse
from app.modules.irt.schemas import (
    ItemCreate,
    ItemOut,
    ItemResponseIn,
    ThetaEstimate,
    ThetaResultSchema,
)

__all__ = [
    "AbilityTheta",
    "Item",
    "ItemCreate",
    "ItemOut",
    "ItemResponse",
    "ItemResponseIn",
    "ThetaEstimate",
    "ThetaResult",
    "ThetaResultSchema",
    "estimate_theta_mle",
    "gradient",
    "hessian",
    "log_likelihood",
    "probability_2pl",
]
