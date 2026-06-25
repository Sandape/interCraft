"""Unit tests for the IRT 2-PL engine (REQ-030 US1).

Per spec US1 acceptance scenarios:
  - "Given (a=1, b=0) with balanced responses, estimated θ ≈ 0 (error < 0.3 logit)"
  - "Given 5 mock responses, system outputs θ + standard_error"
  - "2-PL P(θ) boundary: P(b)=0.5, P(θ→+∞)→1, P(θ→-∞)→0"

Per Constitution III (Test-First), these tests are written BEFORE the
math implementation and verified FAIL. After implementation, they must
all PASS without modification.
"""
from __future__ import annotations

import math

import pytest

from app.modules.irt.engine import (
    DEFAULT_MAX_ITER,
    THETA_BOUND,
    ThetaResult,
    estimate_theta_mle,
    hessian,
    log_likelihood,
    probability_2pl,
)
from app.modules.irt.seed import DIMENSIONS, seed_all_dimensions, seed_items_for_dimension

# ── 2-PL probability ──────────────────────────────────────────────────────


class TestProbability2PL:
    def test_probability_at_difficulty_is_half(self) -> None:
        """P(b; a=1, b=0) == 0.5 exactly (sigmoid(0) = 0.5)."""
        p = probability_2pl(0.0, 1.0, 0.0)
        assert abs(p - 0.5) < 1e-9

    def test_probability_high_theta_approaches_one(self) -> None:
        """P(θ=10; a=1, b=0) > 0.9999 (≫ beyond difficulty)."""
        p = probability_2pl(10.0, 1.0, 0.0)
        assert p > 0.9999

    def test_probability_low_theta_approaches_zero(self) -> None:
        """P(θ=-15; a=1, b=0) < 1e-6 (≪ below difficulty)."""
        # σ(-10) ≈ 4.5e-5, so we go more extreme for the < 1e-6 bound.
        # σ(-15) ≈ 3e-7.
        p = probability_2pl(-15.0, 1.0, 0.0)
        assert p < 1e-6

    def test_probability_monotonic_in_theta(self) -> None:
        """P is strictly increasing in θ (a > 0)."""
        b = 0.5
        a = 1.2
        prev = -1.0
        for theta in [-2.0, -1.0, 0.0, 0.5, 1.0, 2.0, 3.0]:
            p = probability_2pl(theta, a, b)
            assert p > prev, f"non-monotonic at θ={theta}: {p} <= {prev}"
            prev = p

    def test_probability_higher_discrimination_steeper(self) -> None:
        """At θ=1, b=0: a=2 gives higher P than a=1 (steeper slope)."""
        p_low_a = probability_2pl(1.0, 1.0, 0.0)
        p_high_a = probability_2pl(1.0, 2.0, 0.0)
        assert p_high_a > p_low_a

    def test_probability_symmetric_around_b(self) -> None:
        """P(b+d) + P(b-d) ≈ 1 for finite d (logistic symmetry)."""
        b = 0.0
        a = 1.0
        for d in [0.5, 1.0, 2.0]:
            p_above = probability_2pl(b + d, a, b)
            p_below = probability_2pl(b - d, a, b)
            assert abs((p_above + p_below) - 1.0) < 1e-9, (
                f"asymmetry at d={d}: {p_above} + {p_below} = {p_above + p_below}"
            )

    def test_probability_numerically_stable_at_extremes(self) -> None:
        """P does not overflow/underflow for extreme θ values."""
        # Without math.expit, naive sigmoid(±1000) raises OverflowError.
        p_high = probability_2pl(1000.0, 1.0, 0.0)
        p_low = probability_2pl(-1000.0, 1.0, 0.0)
        assert 0.0 <= p_high <= 1.0
        assert 0.0 <= p_low <= 1.0


# ── θ estimation ───────────────────────────────────────────────────────────


class TestEstimateThetaMLE:
    def test_empty_responses_returns_neutral(self) -> None:
        """Zero items → θ=0.0, n_items=0, converged=True, SE=inf."""
        result = estimate_theta_mle([])
        assert result.theta == 0.0
        assert result.n_items == 0
        assert result.converged is True
        assert result.iterations == 0
        assert math.isinf(result.standard_error)

    def test_all_correct_responses_push_theta_high(self) -> None:
        """All correct on items around b=0 → θ̂ > 1.0 (high ability)."""
        # 5 items with b spread around 0; user gets all correct.
        responses = [
            (1.0, -1.0, 1),
            (1.0, -0.5, 1),
            (1.0, 0.0, 1),
            (1.0, 0.5, 1),
            (1.0, 1.0, 1),
        ]
        result = estimate_theta_mle(responses)
        assert result.theta > 1.0, f"expected θ > 1, got {result.theta}"
        assert result.n_items == 5
        assert result.converged is True

    def test_all_incorrect_responses_push_theta_low(self) -> None:
        """All incorrect on items around b=0 → θ̂ < -1.0 (low ability)."""
        responses = [
            (1.0, -1.0, 0),
            (1.0, -0.5, 0),
            (1.0, 0.0, 0),
            (1.0, 0.5, 0),
            (1.0, 1.0, 0),
        ]
        result = estimate_theta_mle(responses)
        assert result.theta < -1.0, f"expected θ < -1, got {result.theta}"
        assert result.n_items == 5
        assert result.converged is True

    def test_recovers_ground_truth_within_tolerance(self) -> None:
        """100 simulated responses with known (a=1, b varying) and θ=0.5
        → estimate within 0.3 logit of true θ (per spec acceptance).

        Uses real response simulation from probability_2pl so the
        ground truth is exactly known — no fixed pattern that could
        accidentally skew the estimate. With 100 items of a=1, the
        standard error is roughly 1/sqrt(100 * 0.25) ≈ 0.2 logits,
        so a single realization is very likely to fall within 0.3
        of the true θ.
        """
        import random

        true_theta = 0.5
        rng = random.Random(42)

        # 100 items, discrimination=1.0, difficulties spanning [-2, +2].
        items = [(1.0, b) for b in (rng.uniform(-2.0, 2.0) for _ in range(100))]

        # Simulate responses from a user with true θ = 0.5.
        responses = []
        for a, b in items:
            p = probability_2pl(true_theta, a, b)
            u = 1 if rng.random() < p else 0
            responses.append((a, b, u))

        result = estimate_theta_mle(responses)
        assert abs(result.theta - true_theta) < 0.3, (
            f"estimate {result.theta} too far from true {true_theta} "
            f"(error {abs(result.theta - true_theta):.3f})"
        )
        assert result.converged is True
        assert result.n_items == 100

    def test_converges_within_max_iter(self) -> None:
        """Standard 5-item case converges in <25 iterations."""
        responses = [
            (1.0, 0.0, 1),
            (1.0, 0.0, 0),
            (1.0, 0.0, 1),
            (1.0, 0.0, 1),
            (1.0, 0.0, 0),
        ]
        result = estimate_theta_mle(responses)
        assert result.converged is True
        assert result.iterations <= 25
        assert result.iterations <= DEFAULT_MAX_ITER

    def test_all_correct_does_not_overflow(self) -> None:
        """All-correct on items of b=0 → no NaN/Inf, finite θ."""
        responses = [(1.0, 0.0, 1)] * 5
        result = estimate_theta_mle(responses)
        assert math.isfinite(result.theta)
        assert math.isfinite(result.standard_error)
        assert not math.isnan(result.theta)

    def test_all_incorrect_does_not_overflow(self) -> None:
        """All-incorrect on items of b=0 → no NaN/Inf, finite θ."""
        responses = [(1.0, 0.0, 0)] * 5
        result = estimate_theta_mle(responses)
        assert math.isfinite(result.theta)
        assert math.isfinite(result.standard_error)
        assert not math.isnan(result.theta)

    def test_standard_error_decreases_with_more_items(self) -> None:
        """SE(5 items) > SE(20 items) — more data → more precise estimate."""
        # 5-item case
        short = [(1.0, 0.0, 1 if i % 2 == 0 else 0) for i in range(5)]
        long_ = [(1.0, 0.0, 1 if i % 2 == 0 else 0) for i in range(20)]
        r5 = estimate_theta_mle(short)
        r20 = estimate_theta_mle(long_)
        assert r5.standard_error > r20.standard_error, (
            f"SE did not decrease: 5-item SE={r5.standard_error}, "
            f"20-item SE={r20.standard_error}"
        )

    def test_zero_discrimination_items_are_skipped(self) -> None:
        """Items with a≈0 contribute no info — θ should not move toward them."""
        # 5 items, all a=0 (no info) and 5 items, a=1, all correct.
        # The estimator should land near the a=1 items' b values, not θ=0.
        no_info = [(0.0, 0.0, 0)] * 5
        result_no_info = estimate_theta_mle(no_info)
        # With zero info, the gradient is 0 from those items. Plus the
        # base prior pull toward θ=0 via the iteration initialization.
        # Expect result around 0 (no evidence to push either way).
        assert abs(result_no_info.theta) < 0.5

        # With informative items alongside, the θ should reflect the
        # informative items' data.
        mixed = no_info + [(1.0, 0.0, 1)] * 5
        result_mixed = estimate_theta_mle(mixed)
        # All correct on b=0 items → θ should be high.
        assert result_mixed.theta > 0.5, (
            f"expected θ > 0.5 with 5 all-correct informative items, "
            f"got {result_mixed.theta}"
        )

    def test_theta_bounded_to_plausible_range(self) -> None:
        """Even with extreme items, θ̂ stays in [-THETA_BOUND, +THETA_BOUND]."""
        # All-correct on 100 items with b=+5 (impossibly hard).
        responses = [(1.0, 5.0, 1)] * 100
        result = estimate_theta_mle(responses)
        assert -THETA_BOUND <= result.theta <= THETA_BOUND

    def test_log_likelihood_at_mle_is_maximum(self) -> None:
        """The estimated θ maximizes the log-likelihood among nearby points."""
        responses = [
            (1.0, 0.0, 1),
            (1.0, 0.5, 1),
            (1.0, 1.0, 0),
            (1.0, -0.5, 0),
        ]
        result = estimate_theta_mle(responses)
        ll_at_hat = log_likelihood(result.theta, responses)
        # Sample nearby θ values; LL should be ≤ LL at θ̂.
        for delta in [-0.5, -0.2, -0.1, 0.1, 0.2, 0.5]:
            ll_test = log_likelihood(result.theta + delta, responses)
            assert ll_test <= ll_at_hat + 1e-6, (
                f"LL({result.theta + delta})={ll_test} > LL({result.theta})={ll_at_hat}"
            )

    def test_hessian_negative_at_interior(self) -> None:
        """Hessian is strictly negative for a > 0 (concave log-likelihood)."""
        responses = [(1.0, 0.0, 1), (1.0, 1.0, 0), (1.5, -0.5, 1)]
        for theta in [-2.0, -1.0, 0.0, 1.0, 2.0]:
            h = hessian(theta, responses)
            assert h < 0, f"H({theta}) = {h} should be negative"

    def test_theta_result_is_dataclass(self) -> None:
        """Sanity check: ThetaResult is the documented shape."""
        result = estimate_theta_mle([(1.0, 0.0, 1)])
        assert isinstance(result, ThetaResult)
        assert hasattr(result, "theta")
        assert hasattr(result, "standard_error")
        assert hasattr(result, "n_items")
        assert hasattr(result, "converged")
        assert hasattr(result, "iterations")


# ── Seed loader ────────────────────────────────────────────────────────────


class TestSeedLoader:
    def test_seed_items_for_dimension_returns_ten(self) -> None:
        """Each dimension has exactly 10 seed items."""
        for dim in DIMENSIONS:
            items = seed_items_for_dimension(dim)
            assert len(items) == 10, f"{dim}: expected 10, got {len(items)}"
            for item in items:
                assert item.dimension == dim
                assert -6.0 <= item.difficulty_b <= 6.0
                assert 0.0 <= item.discrimination_a <= 5.0
                assert item.model == "2pl"
                assert item.status == "uncalibrated"

    def test_seed_items_are_dimensionally_distinct(self) -> None:
        """Items in different dimensions have distinct question_text_hash."""
        hashes_by_dim: dict[str, set[str]] = {}
        for dim in DIMENSIONS:
            items = seed_items_for_dimension(dim)
            hashes_by_dim[dim] = {i.question_text_hash for i in items}
        # Cross-dimension: at least one hash collision would be a bug.
        all_hashes = []
        for _dim, hashes in hashes_by_dim.items():
            all_hashes.extend(hashes)
        assert len(all_hashes) == len(set(all_hashes)), (
            "duplicate question_text_hash across dimensions"
        )

    def test_seed_all_dimensions_returns_fifty(self) -> None:
        """5 dimensions × 10 items = 50 seed items total."""
        items = seed_all_dimensions()
        assert len(items) == 50
        # All 5 dimensions represented.
        from collections import Counter

        counts = Counter(i.dimension for i in items)
        for dim in DIMENSIONS:
            assert counts[dim] == 10

    def test_seed_difficulty_ladder_covers_range(self) -> None:
        """Seed difficulties span a meaningful logit range."""
        items = seed_items_for_dimension("tech_depth")
        difficulties = sorted(i.difficulty_b for i in items)
        # Min ≤ -1.5, max ≥ +2.0
        assert difficulties[0] <= -1.5
        assert difficulties[-1] >= 2.0
        # Range ≥ 4 logits.
        assert difficulties[-1] - difficulties[0] >= 4.0

    def test_seed_rejects_unknown_dimension(self) -> None:
        """Calling seed with an unknown dimension raises ValueError."""
        with pytest.raises(ValueError, match="unknown dimension"):
            seed_items_for_dimension("not_a_real_dimension")


# ── Integration with seed items ────────────────────────────────────────────


class TestEngineWithSeedItems:
    """End-to-end: feed seed item parameters back into the engine."""

    def test_balanced_responses_to_seed_recovers_theta_zero(self) -> None:
        """Seed items (a=1-ish) + balanced correct/incorrect → θ̂ ≈ 0."""
        items = seed_items_for_dimension("tech_depth")
        # Take items in the central logit band (|b| <= 0.8). The seed
        # ladder places b = -0.7, -0.2, +0.3, +0.8 in this range (4 items).
        centered = [it for it in items if abs(it.difficulty_b) <= 0.8]
        assert len(centered) >= 3, "test setup expects at least 3 centered items"
        responses = []
        for i, it in enumerate(centered):
            u = 1 if i % 2 == 0 else 0  # alternating correct/incorrect
            responses.append((it.discrimination_a, it.difficulty_b, u))

        result = estimate_theta_mle(responses)
        # θ̂ should be near 0; tolerance 0.3 logit per spec.
        assert abs(result.theta) < 0.3, (
            f"θ̂ = {result.theta} not within 0.3 of 0 for balanced responses"
        )
