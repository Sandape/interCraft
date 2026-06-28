"""REQ-033 US4 T107 — Pure cost calculator for AI invocations.

This module is the canonical USD cost estimator used by the LLM client
(``app.agents.llm_client._build_ai_invocation_summary``) and by the PM
Dashboard AI Operations panel (``pm_dashboard.service.get_ai_operations``).

Why a pure module (no DB, no async, no I/O)?

- The cost is a *function* of (prompt_tokens, completion_tokens, model).
  No dependency on time, environment, or persistent state.
- Pure functions are trivially unit-testable: just call
  ``estimate_cost(1000, 500, "gpt-4o-mini")`` and assert the float.
- The PM Dashboard reports the same cost the LLM client recorded — the
  contract is ``estimate_cost(prompt, completion, model) == summary.estimated_cost``
  for matching inputs, so a single function powers both sides.

Rate table semantics:

- ``MODEL_RATES`` maps canonical model name → (prompt_rate_per_1k_usd,
  completion_rate_per_1k_usd). The rates are USD per **1,000 tokens**;
  the cost formula divides by 1,000 to get the per-token rate then
  multiplies by the token count.
- The ``"mock"`` model rate is 0.0 — tests that exercise the LLM
  pipeline in mock mode should see $0.00 estimated cost.
- An unknown model falls back to ``FALLBACK_PROMPT_RATE`` /
  ``FALLBACK_COMPLETION_RATE`` (a conservative low estimate). The PM
  dashboard surfaces the rate via the panel's source-of-truth label so
  PM can spot when a new model sneaks in.

These rates are deliberately conservative estimates (FR-008 "labeled
estimate"). They are NOT for billing — the ``is_estimate=True`` flag on
``AIInvocationSummary`` is the explicit contract that downstream
consumers must read.

Sanity check (T102): 1000 prompt + 500 completion on gpt-4o-mini →
(1000/1000) * 0.00015 + (500/1000) * 0.0006 = 0.00015 + 0.0003 = 0.00045 USD.
"""
from __future__ import annotations

#: Per-model USD rate per **1,000 tokens**: (prompt, completion).
#:
#: Reference rates (per 1k, conservative side):
#:
#: - gpt-4o:        $0.0025 / $0.01
#: - gpt-4o-mini:   $0.00015 / $0.0006
#: - deepseek-chat: $0.00014 / $0.00028
#: - deepseek-coder:$0.00014 / $0.00028
#: - mock:          $0.0 / $0.0
#:
#: When a new model lands in production without being added here, the
#: ``FALLBACK_*`` rates apply so the cost column is never NULL/NaN.
MODEL_RATES: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "deepseek-chat": (0.00014, 0.00028),
    "deepseek-coder": (0.00014, 0.00028),
    "mock": (0.0, 0.0),
}

#: Fallback rate (per 1k tokens) when model is missing from ``MODEL_RATES``.
#: Conservative low estimate; the panel labels the cost as an estimate
#: so PM sees the rate via source-of-truth if they need to audit.
FALLBACK_PROMPT_RATE: float = 0.001
FALLBACK_COMPLETION_RATE: float = 0.002


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Estimate USD cost for an AI call.

    Args:
        prompt_tokens: Number of prompt (input) tokens consumed. Negative
            values are clamped to 0 (defensive — never bill a negative).
        completion_tokens: Number of completion (output) tokens generated.
            Negative values are clamped to 0.
        model: Canonical model name (case-sensitive). Must match a key
            in ``MODEL_RATES``; otherwise the fallback rate applies.

    Returns:
        Estimated USD cost as a float, always >= 0.0. Zero tokens →
        zero cost; unknown model → cost at the fallback rate (still
        > 0 unless tokens are zero).
    """
    p = max(0, int(prompt_tokens))
    c = max(0, int(completion_tokens))
    prompt_rate, completion_rate = MODEL_RATES.get(
        model, (FALLBACK_PROMPT_RATE, FALLBACK_COMPLETION_RATE)
    )
    # Rates are per 1,000 tokens.
    cost = (p / 1000.0) * prompt_rate + (c / 1000.0) * completion_rate
    # Clamp at 0.0 to defend against negative-rate bugs in the table.
    return max(0.0, float(cost))


__all__ = [
    "FALLBACK_COMPLETION_RATE",
    "FALLBACK_PROMPT_RATE",
    "MODEL_RATES",
    "estimate_cost",
]
