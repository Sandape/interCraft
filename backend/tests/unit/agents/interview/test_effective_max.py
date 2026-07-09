"""[REQ-048 US3 T063] Unit test for effective_max calculation.

AC-12a (constant boundary, R3) + AC-12b (dynamic 7-15, R3) + AC-15 (legacy
default compat, R12) coverage. The effective_max formula is locked at
``max(MIN_QUESTIONS_FULL=7, min(user_choice, planner_recommended))``
(FR-023, plan.md R-6). Constants vs dynamic split per AC-12a/AC-12b.

These tests import from ``app.agents.interview.effective_max`` — that
helper is created in T067 (Batch C). If the helper module is missing
the test will fail with ``ModuleNotFoundError`` (correct TDD red phase).
"""
from __future__ import annotations

import pytest

from app.agents.interview.effective_max import (
    MIN_QUESTIONS_FULL,
    MAX_QUESTIONS_FULL,
    HARD_MIN_QUESTIONS_FULL,
    HARD_MAX_QUESTIONS_FULL,
    compute_effective_max,
    compute_planner_recommended,
    compute_effective_max_for_legacy,
)


# ---------------------------------------------------------------------------
# AC-12a — constant boundary (4 cases). (R3 + R16)
# ---------------------------------------------------------------------------


def test_boundary_user_eq_planner_10() -> None:
    """user=10, planner=10 → 10 (no clamp)."""
    assert compute_effective_max(user_choice=10, planner_recommended=10) == 10


def test_boundary_user_eq_planner_15() -> None:
    """user=15, planner=15 → 15 (no clamp)."""
    assert compute_effective_max(user_choice=15, planner_recommended=15) == 15


def test_boundary_user_10_planner_5_hits_hard_min() -> None:
    """user=10, planner=5 → 7 (planner < hard_min → clamp to hard_min)."""
    assert compute_effective_max(user_choice=10, planner_recommended=5) == HARD_MIN_QUESTIONS_FULL
    assert HARD_MIN_QUESTIONS_FULL == 7


def test_boundary_user_15_planner_20_hits_hard_max() -> None:
    """user=15, planner=20 → 15 (min(user, planner) = 15)."""
    assert compute_effective_max(user_choice=15, planner_recommended=20) == 15


# ---------------------------------------------------------------------------
# AC-12b — dynamic planner_recommended in [7, 15] (4 cases). (R3)
# ---------------------------------------------------------------------------


def test_dynamic_user_10_planner_8() -> None:
    """user=10, planner=8 → 8 (no clamp — both in envelope)."""
    assert compute_effective_max(user_choice=10, planner_recommended=8) == 8


def test_dynamic_user_15_planner_9() -> None:
    """user=15, planner=9 → 9 (no clamp)."""
    assert compute_effective_max(user_choice=15, planner_recommended=9) == 9


def test_dynamic_user_10_planner_12_caps_to_user() -> None:
    """user=10, planner=12 → 10 (min(user, planner) = 10)."""
    assert compute_effective_max(user_choice=10, planner_recommended=12) == 10


def test_dynamic_user_15_planner_14() -> None:
    """user=15, planner=14 → 14 (no clamp)."""
    assert compute_effective_max(user_choice=15, planner_recommended=14) == 14


# ---------------------------------------------------------------------------
# Constants are locked.
# ---------------------------------------------------------------------------


def test_constants_locked() -> None:
    """The envelope is hard-locked at [7, 15] per FR-023."""
    assert MIN_QUESTIONS_FULL == 7
    assert MAX_QUESTIONS_FULL == 15
    assert HARD_MIN_QUESTIONS_FULL == 7
    assert HARD_MAX_QUESTIONS_FULL == 15


# ---------------------------------------------------------------------------
# compute_planner_recommended — focus_areas × 3-5 题. (FR-023)
# ---------------------------------------------------------------------------


def test_planner_recommended_3_focus_areas_picks_midpoint() -> None:
    """3 focus_areas × [3,5] → 12 (midpoint 4 × 3 = 12)."""
    assert compute_planner_recommended(focus_area_count=3) == 12


def test_planner_recommended_4_focus_areas() -> None:
    """4 focus_areas × midpoint 4 → 16 → capped to hard_max 15."""
    assert compute_planner_recommended(focus_area_count=4) == HARD_MAX_QUESTIONS_FULL


def test_planner_recommended_5_focus_areas() -> None:
    """5 focus_areas × midpoint 4 → 20 → capped to hard_max 15."""
    assert compute_planner_recommended(focus_area_count=5) == HARD_MAX_QUESTIONS_FULL


def test_planner_recommended_2_focus_areas_floors_at_hard_min() -> None:
    """2 focus_areas × midpoint 4 → 8 (within envelope)."""
    assert compute_planner_recommended(focus_area_count=2) == 8


def test_planner_recommended_1_focus_area_floors_at_hard_min() -> None:
    """1 focus_area × midpoint 4 → 4 → floors to hard_min 7."""
    assert compute_planner_recommended(focus_area_count=1) == HARD_MIN_QUESTIONS_FULL


def test_planner_recommended_0_focus_areas_uses_default() -> None:
    """0 focus_areas (edge) → default 7 (hard_min)."""
    assert compute_planner_recommended(focus_area_count=0) == HARD_MIN_QUESTIONS_FULL


# ---------------------------------------------------------------------------
# AC-15 — legacy session (max_questions=5) → effective_max=7 (R12).
# ---------------------------------------------------------------------------


def test_legacy_session_max_questions_5_yields_effective_max_7() -> None:
    """Legacy session that stored max_questions=5 (DEFAULT before 0028)
    must still compute to effective_max=7 per FR-023."""
    assert compute_effective_max_for_legacy(stored_max_questions=5) == 7


def test_legacy_session_max_questions_none_yields_hard_min() -> None:
    """If max_questions is NULL (post-migration quick_drill/doubao rows),
    fall back to hard_min."""
    assert compute_effective_max_for_legacy(stored_max_questions=None) == HARD_MIN_QUESTIONS_FULL


def test_legacy_session_max_questions_10_yields_10() -> None:
    """Legacy session with stored max_questions=10 keeps 10."""
    assert compute_effective_max_for_legacy(stored_max_questions=10) == 10


# ---------------------------------------------------------------------------
# AC-12a (R16) — migration 0028 SQL assertions: NOT VALID + VALIDATE.
# ---------------------------------------------------------------------------


def test_migration_0028_uses_not_valid_for_max_questions_check() -> None:
    """AC-12a R16: migration 0028 must add the CHECK constraint as
    ``NOT VALID`` first so legacy `max_questions=5` rows don't fail
    the upgrade. The follow-up ``VALIDATE CONSTRAINT`` runs separately
    after the application has backfilled.

    We assert this by reading the migration file and checking it
    contains the ``NOT VALID`` + ``VALIDATE CONSTRAINT`` markers.
    """
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "0028_interview_mode_split.py"
    )
    if not migration_path.exists():
        pytest.skip(f"migration not found: {migration_path}")
    content = migration_path.read_text(encoding="utf-8")
    # The migration MUST use NOT VALID for the max_questions CHECK to
    # avoid legacy max_questions=5 rows triggering CheckViolation during
    # ``alembic upgrade head``. (R16)
    assert "NOT VALID" in content, (
        "migration 0028 must use NOT VALID for the max_questions CHECK "
        "constraint to avoid legacy max_questions=5 rows triggering "
        "CheckViolation (AC-12a R16)"
    )
    # And MUST subsequently run VALIDATE CONSTRAINT.
    assert "VALIDATE CONSTRAINT" in content, (
        "migration 0028 must run VALIDATE CONSTRAINT after NOT VALID "
        "to actually enforce the check post-backfill (AC-12a R16)"
    )


# ---------------------------------------------------------------------------
# Edge / parametrized
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user_choice", "planner_recommended", "expected"),
    [
        (10, 10, 10),
        (15, 15, 15),
        (10, 5, 7),
        (15, 20, 15),
        (10, 8, 8),
        (15, 9, 9),
        (10, 12, 10),
        (15, 14, 14),
    ],
)
def test_effective_max_matrix(user_choice, planner_recommended, expected) -> None:
    """Combined AC-12a + AC-12b matrix (8 cases) per AC description."""
    assert compute_effective_max(
        user_choice=user_choice, planner_recommended=planner_recommended
    ) == expected


def test_effective_max_user_choice_out_of_envelope_raises() -> None:
    """user_choice outside [7,15] is a programmer error — raise ValueError."""
    with pytest.raises(ValueError):
        compute_effective_max(user_choice=5, planner_recommended=10)
    with pytest.raises(ValueError):
        compute_effective_max(user_choice=20, planner_recommended=10)


def test_effective_max_planner_recommended_clamps_to_envelope() -> None:
    """planner_recommended outside [7,15] is CLAMPED (not raised) — this is
    the AC-12a boundary behaviour. Per FR-023 the formula must clamp
    regardless of how extreme the planner value is."""
    # planner=4 → min(10,4)=4 → clamp to 7
    assert compute_effective_max(user_choice=10, planner_recommended=4) == 7
    # planner=21 → min(10,21)=10 → clamp to 10 (already in envelope)
    assert compute_effective_max(user_choice=10, planner_recommended=21) == 10
    # planner=100 → min(10,100)=10 → 10
    assert compute_effective_max(user_choice=10, planner_recommended=100) == 10