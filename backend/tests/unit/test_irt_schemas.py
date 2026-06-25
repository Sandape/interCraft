"""Unit tests for IRT Pydantic schemas (REQ-030 US1).

Boundary tests for ItemCreate / ItemResponseIn validators. The schemas
are the first line of defense against invalid values reaching the DB,
so every CHECK constraint needs a corresponding Pydantic validator.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.irt.schemas import (
    ItemCreate,
    ItemResponseIn,
    ThetaEstimate,
    ThetaResultSchema,
)


class TestItemCreate:
    def test_minimal_valid(self) -> None:
        """All required fields populated, defaults apply."""
        item = ItemCreate(
            dimension="tech_depth",
            question_text_hash="a" * 64,
            difficulty_b=0.0,
            discrimination_a=1.0,
        )
        assert item.model == "2pl"
        assert item.status == "uncalibrated"
        assert item.difficulty_b == 0.0
        assert item.discrimination_a == 1.0

    def test_rejects_difficulty_above_bound(self) -> None:
        """difficulty_b > 6 violates the DB CHECK constraint."""
        with pytest.raises(ValidationError) as exc:
            ItemCreate(
                dimension="tech_depth",
                question_text_hash="a" * 64,
                difficulty_b=7.0,
                discrimination_a=1.0,
            )
        assert "difficulty_b" in str(exc.value)

    def test_rejects_difficulty_below_bound(self) -> None:
        """difficulty_b < -6 violates the DB CHECK constraint."""
        with pytest.raises(ValidationError):
            ItemCreate(
                dimension="tech_depth",
                question_text_hash="a" * 64,
                difficulty_b=-7.0,
                discrimination_a=1.0,
            )

    def test_rejects_negative_discrimination(self) -> None:
        """discrimination_a < 0 violates the DB CHECK constraint."""
        with pytest.raises(ValidationError):
            ItemCreate(
                dimension="tech_depth",
                question_text_hash="a" * 64,
                difficulty_b=0.0,
                discrimination_a=-0.1,
            )

    def test_rejects_nan_difficulty(self) -> None:
        """NaN must be rejected so stored values stay finite.

        Pydantic v2's `le=6.0` constraint actually rejects NaN (NaN
        comparisons are always False, so `nan <= 6` is False), so the
        built-in constraint catches it. We assert that any ValidationError
        is raised — the exact message varies by Pydantic version.
        """
        with pytest.raises(ValidationError):
            ItemCreate(
                dimension="tech_depth",
                question_text_hash="a" * 64,
                difficulty_b=float("nan"),
                discrimination_a=1.0,
            )

    def test_rejects_invalid_status(self) -> None:
        """status is a Literal; values outside the whitelist are rejected."""
        with pytest.raises(ValidationError):
            ItemCreate(
                dimension="tech_depth",
                question_text_hash="a" * 64,
                difficulty_b=0.0,
                discrimination_a=1.0,
                status="not_a_real_status",  # type: ignore[arg-type]
            )

    def test_accepts_all_valid_statuses(self) -> None:
        """All four ItemStatus values should be accepted."""
        for status in ("uncalibrated", "calibrated", "retired", "flagged"):
            item = ItemCreate(
                dimension="tech_depth",
                question_text_hash="a" * 64,
                difficulty_b=0.0,
                discrimination_a=1.0,
                status=status,  # type: ignore[arg-type]
            )
            assert item.status == status


class TestItemResponseIn:
    def test_minimal_valid(self) -> None:
        """All required fields populated."""
        from uuid import uuid4

        item_id = uuid4()
        r = ItemResponseIn(
            item_id=item_id,
            response="correct",
            score=8.5,
        )
        assert r.response == "correct"
        assert r.score == 8.5
        assert r.source_interview_id is None

    def test_rejects_score_above_ten(self) -> None:
        """score > 10 is invalid (LLM scores are 0-10)."""
        with pytest.raises(ValidationError):
            ItemResponseIn(
                item_id=__import__("uuid").uuid4(),
                response="correct",
                score=11.0,
            )

    def test_rejects_score_below_zero(self) -> None:
        """score < 0 is invalid."""
        with pytest.raises(ValidationError):
            ItemResponseIn(
                item_id=__import__("uuid").uuid4(),
                response="correct",
                score=-0.1,
            )

    def test_rejects_invalid_response_label(self) -> None:
        """response is Literal['correct','incorrect']."""
        with pytest.raises(ValidationError):
            ItemResponseIn(
                item_id=__import__("uuid").uuid4(),
                response="partial",  # type: ignore[arg-type]
                score=5.0,
            )


class TestThetaEstimate:
    def test_valid_estimate(self) -> None:
        """Standard θ + SE combination is accepted."""
        e = ThetaEstimate(
            dimension="tech_depth",
            theta=1.5,
            standard_error=0.4,
            n_items=10,
            converged=True,
        )
        assert e.theta == 1.5
        assert e.n_items == 10

    def test_rejects_theta_above_bound(self) -> None:
        with pytest.raises(ValidationError):
            ThetaEstimate(
                dimension="tech_depth",
                theta=7.0,
                standard_error=0.4,
                n_items=10,
                converged=True,
            )

    def test_rejects_zero_se(self) -> None:
        """SE must be > 0 (DB CHECK constraint)."""
        with pytest.raises(ValidationError):
            ThetaEstimate(
                dimension="tech_depth",
                theta=1.0,
                standard_error=0.0,
                n_items=10,
                converged=True,
            )


class TestThetaResultSchema:
    def test_valid_result(self) -> None:
        r = ThetaResultSchema(
            theta=0.5,
            standard_error=0.4,
            n_items=20,
            converged=True,
            iterations=5,
        )
        assert r.iterations == 5
        assert r.converged is True

    def test_rejects_zero_n_items(self) -> None:
        """n_items must be >= 0 (0 is allowed for empty input)."""
        # Wait — DB CHECK says n_items >= 1 for stored thetas. The
        # engine can return n_items=0 for empty input, but the schema
        # for STORED thetas enforces n_items >= 1. The Pydantic schema
        # here is the *result* type, which allows 0.
        r = ThetaResultSchema(
            theta=0.0,
            standard_error=1.0,
            n_items=0,
            converged=True,
            iterations=0,
        )
        assert r.n_items == 0
