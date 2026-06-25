"""Seed items for the IRT bank (REQ-030 US1).

US1 ships with hardcoded seed items per dimension. The parameters are
chosen to span the practical ability range and provide discriminating
information across the θ distribution — they're NOT calibrated from real
data, just reasonable priors that exercise the math pipeline end-to-end.

US3 (deferred) will replace the seed with parameters calibrated from
historical interview responses via marginal MLE.

Difficulty distribution: b ∈ {-2, -1.3, -0.7, -0.2, +0.3, +0.8, +1.3, +1.7, +2.0, +2.5}
    Roughly equal coverage of the [-2, +2.5] logit range, with extra density
    in the middle (most users) and tail coverage (extreme abilities).
Discrimination: a ∈ {0.8, 1.0, 1.2, 1.5}, cycling — some "easy" items
    (low a) and some "highly discriminating" items (high a). Items with
    a > 2.5 are too peaky and noisy in practice.

Each dimension has exactly 10 items. The hash is deterministic (sha256 of
dimension + ordinal) so re-seeding is idempotent.
"""
from __future__ import annotations

import hashlib

from app.modules.irt.schemas import ItemCreate

# Five core interview dimensions — mirror DIMENSIONS in
# `backend/app/agents/interview/nodes/question_gen.py`. US1 keeps the
# same surface so the bank integrates with the existing interview flow.
DIMENSIONS: tuple[str, ...] = (
    "tech_depth",
    "architecture",
    "engineering_practice",
    "communication",
    "algorithm",
)

# Difficulty ladder (10 steps) — 10 items per dimension will pick from
# this in order. Chosen to cover the practical ability range.
_DIFFICULTY_LADDER: tuple[float, ...] = (
    -2.0, -1.3, -0.7, -0.2, 0.3, 0.8, 1.3, 1.7, 2.0, 2.5,
)

# Discrimination cycle (4 values) — 10 items pick 0..9 mod 4.
_DISCRIMINATION_CYCLE: tuple[float, ...] = (0.8, 1.0, 1.2, 1.5)


def _seed_hash(dimension: str, ordinal: int) -> str:
    """Deterministic 64-char hex hash for a (dimension, ordinal) pair.

    SHA-256 truncated to 64 hex chars (the `question_text_hash` column is
    sized for that). The hash is stable across re-runs so seed operations
    are idempotent (the partial unique index
    `uq_irt_items_active_dim_hash` catches duplicates).
    """
    raw = f"{dimension}:seed:{ordinal}".encode()
    return hashlib.sha256(raw).hexdigest()[:64]


def seed_items_for_dimension(dimension: str) -> list[ItemCreate]:
    """Return 10 seed `ItemCreate` rows for one dimension.

    The list is exactly 10 items long with `difficulty_b` drawn from
    `_DIFFICULTY_LADDER` and `discrimination_a` cycling through
    `_DISCRIMINATION_CYCLE`. All items start as `status="uncalibrated"`
    (US1 doesn't run calibration; that's US3).
    """
    if dimension not in DIMENSIONS:
        raise ValueError(
            f"unknown dimension {dimension!r}; expected one of {DIMENSIONS}"
        )
    items: list[ItemCreate] = []
    for ordinal, b in enumerate(_DIFFICULTY_LADDER):
        a = _DISCRIMINATION_CYCLE[ordinal % len(_DISCRIMINATION_CYCLE)]
        items.append(
            ItemCreate(
                dimension=dimension,
                question_text_hash=_seed_hash(dimension, ordinal),
                difficulty_b=b,
                discrimination_a=a,
                model="2pl",
                status="uncalibrated",
            )
        )
    return items


def seed_all_dimensions() -> list[ItemCreate]:
    """Return 5 × 10 = 50 seed `ItemCreate` rows covering all dimensions."""
    out: list[ItemCreate] = []
    for dim in DIMENSIONS:
        out.extend(seed_items_for_dimension(dim))
    return out


__all__ = ["DIMENSIONS", "seed_all_dimensions", "seed_items_for_dimension"]
