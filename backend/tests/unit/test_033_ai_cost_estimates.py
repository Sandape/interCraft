"""REQ-033 US4 T102 — Cost-estimator unit tests.

Locks the contract of ``app.modules.telemetry_contracts.costs.estimate_cost``
so the LLM client hook and the PM Dashboard AI Operations panel compute
the same USD cost for matching (prompt_tokens, completion_tokens, model)
inputs.

Why a unit test (not integration)?

- ``estimate_cost`` is a pure function with no IO. Per the spec, it must
  be testable in isolation (T107: "pure function, no DB / no async").
- The TDD rule: tests must FAIL before T107 lands, PASS after. The
  implementation is in ``app/modules/telemetry_contracts/costs.py``.

Coverage:

- 0 tokens → 0.0 cost (zero division / zero multiplication guard).
- 1000 prompt + 500 completion on gpt-4o-mini → known USD value derived
  from the published rate.
- Mock model → always 0.0 (test pipeline must not bill a fake call).
- Unknown model → fallback rate applies (defensive — never returns None).
- Negative token counts → clamped to 0 (defensive — never bill a
  negative amount).
- Pure function: no global state, no async, idempotent on repeat calls.
- All known canonical models (``gpt-4o``, ``gpt-4o-mini``,
  ``deepseek-chat``, ``deepseek-coder``, ``mock``) appear in
  ``MODEL_RATES`` so the LLM client + dashboard never hit fallback.
"""
from __future__ import annotations

import pytest

from app.modules.telemetry_contracts.costs import (
    FALLBACK_COMPLETION_RATE,
    FALLBACK_PROMPT_RATE,
    MODEL_RATES,
    estimate_cost,
)


# ---------------------------------------------------------------------------
# T102 — Zero-tokens guard
# ---------------------------------------------------------------------------


def test_estimate_cost_zero_tokens_returns_zero() -> None:
    """0 prompt + 0 completion → cost == 0.0 for any model."""
    assert estimate_cost(0, 0, "gpt-4o-mini") == 0.0
    assert estimate_cost(0, 0, "gpt-4o") == 0.0
    assert estimate_cost(0, 0, "deepseek-chat") == 0.0
    assert estimate_cost(0, 0, "mock") == 0.0
    assert estimate_cost(0, 0, "unknown-future-model") == 0.0


def test_estimate_cost_only_prompt_tokens() -> None:
    """Only prompt tokens set: cost = (p/1000) * prompt_rate."""
    # gpt-4o-mini prompt rate = $0.00015 / 1k
    # 1000 prompt tokens → 0.00015 USD
    assert estimate_cost(1000, 0, "gpt-4o-mini") == pytest.approx(0.00015)


def test_estimate_cost_only_completion_tokens() -> None:
    """Only completion tokens set: cost = (c/1000) * completion_rate."""
    # gpt-4o-mini completion rate = $0.0006 / 1k
    # 500 completion tokens → 0.0003 USD
    assert estimate_cost(0, 500, "gpt-4o-mini") == pytest.approx(0.0003)


# ---------------------------------------------------------------------------
# T102 — Per-model rate correctness (gpt-4o-mini sanity check)
# ---------------------------------------------------------------------------


def test_estimate_cost_gpt4o_mini_published_rate() -> None:
    """1000 prompt + 500 completion on gpt-4o-mini:
    prompt  = (1000/1000) * 0.00015 = 0.00015
    compl.  = (500/1000)  * 0.0006  = 0.0003
    total   = 0.00045 USD
    """
    assert estimate_cost(1000, 500, "gpt-4o-mini") == pytest.approx(0.00045)


def test_estimate_cost_gpt4o_published_rate() -> None:
    """1000 prompt + 500 completion on gpt-4o:
    prompt  = (1000/1000) * 0.0025 = 0.0025
    compl.  = (500/1000)  * 0.01   = 0.005
    total   = 0.0075 USD
    """
    assert estimate_cost(1000, 500, "gpt-4o") == pytest.approx(0.0075)


def test_estimate_cost_deepseek_chat_published_rate() -> None:
    """1000 prompt + 500 completion on deepseek-chat:
    prompt  = (1000/1000) * 0.00014 = 0.00014
    compl.  = (500/1000)  * 0.00028 = 0.00014
    total   = 0.00028 USD
    """
    assert estimate_cost(1000, 500, "deepseek-chat") == pytest.approx(0.00028)


# ---------------------------------------------------------------------------
# T102 — Mock model zero rate
# ---------------------------------------------------------------------------


def test_estimate_cost_mock_model_is_zero() -> None:
    """Mock model rate is 0.0 — the test pipeline must never bill."""
    assert estimate_cost(0, 0, "mock") == 0.0
    assert estimate_cost(10_000, 5_000, "mock") == 0.0
    assert estimate_cost(1_000_000, 1_000_000, "mock") == 0.0


# ---------------------------------------------------------------------------
# T102 — Unknown model fallback
# ---------------------------------------------------------------------------


def test_estimate_cost_unknown_model_uses_fallback() -> None:
    """Unknown model → FALLBACK rates, never None / never NaN."""
    cost = estimate_cost(1000, 1000, "totally-unknown-model-xyz")
    expected = FALLBACK_PROMPT_RATE + FALLBACK_COMPLETION_RATE
    assert cost == pytest.approx(expected)


def test_estimate_cost_empty_model_string_uses_fallback() -> None:
    """Empty model string → fallback rate (defensive)."""
    cost = estimate_cost(1000, 0, "")
    expected = FALLBACK_PROMPT_RATE
    assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# T102 — Defensive: negative token counts clamped
# ---------------------------------------------------------------------------


def test_estimate_cost_negative_tokens_clamped_to_zero() -> None:
    """Negative prompt/completion tokens → clamped to 0, cost = 0."""
    assert estimate_cost(-100, -100, "gpt-4o-mini") == 0.0
    assert estimate_cost(-100, 500, "gpt-4o-mini") == pytest.approx(0.0003)
    assert estimate_cost(1000, -100, "gpt-4o-mini") == pytest.approx(0.00015)


# ---------------------------------------------------------------------------
# T102 — Pure function invariants
# ---------------------------------------------------------------------------


def test_estimate_cost_is_pure_and_idempotent() -> None:
    """Same inputs → same output, no global state mutation."""
    inputs = (2000, 800, "gpt-4o-mini")
    first = estimate_cost(*inputs)
    second = estimate_cost(*inputs)
    third = estimate_cost(*inputs)
    assert first == second == third
    # Different arguments must produce different costs (sanity).
    assert estimate_cost(2000, 800, "gpt-4o-mini") != estimate_cost(
        2000, 800, "gpt-4o"
    )


def test_estimate_cost_returns_float() -> None:
    """``estimate_cost`` always returns a float (never Decimal, int)."""
    result = estimate_cost(100, 100, "gpt-4o-mini")
    assert isinstance(result, float)
    assert result >= 0.0


# ---------------------------------------------------------------------------
# T102 — MODEL_RATES table completeness
# ---------------------------------------------------------------------------


def test_model_rates_includes_all_canonical_models() -> None:
    """All canonical model names must appear in ``MODEL_RATES``.

    Missing a canonical model means the LLM client hook would silently
    fall back to the (lower) fallback rate, which under-reports cost.
    This test fails loud if a model is removed from the table.
    """
    canonical = {"gpt-4o", "gpt-4o-mini", "deepseek-chat", "deepseek-coder", "mock"}
    assert canonical.issubset(MODEL_RATES.keys()), (
        f"MODEL_RATES missing canonical models: {canonical - MODEL_RATES.keys()}"
    )


def test_model_rates_values_are_non_negative() -> None:
    """Every rate tuple in ``MODEL_RATES`` must have non-negative values.

    A negative rate would silently produce a negative cost — defensive
    guard against a typo in the table.
    """
    for model, rates in MODEL_RATES.items():
        prompt_rate, completion_rate = rates
        assert prompt_rate >= 0.0, f"{model} prompt_rate {prompt_rate} < 0"
        assert completion_rate >= 0.0, (
            f"{model} completion_rate {completion_rate} < 0"
        )
