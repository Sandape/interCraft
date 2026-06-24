"""Golden cases integration test (Phase 4 TDD - T031).

Replays all 10 golden cases through the real node functions (score_node /
report_node) with the LLM client stubbed to yield the case's `llm_response`.

This is the CI-runnable eval gate (FR-010, FR-014). Run with:
    uv run pytest tests/eval/test_golden_cases.py -q

Case-by-case expectations:
- 8 normal cases (Chinese output, expected_fidelity_pass=True) → pass
- 2 regression cases (English output, expected_fidelity_pass=False) → also
  pass (the checker correctly flags the English output, which is what the
  case validates — if the checker missed it, the case would fail with
  `checker_failed_to_flag_expected_regression`)

SC-003 validation: 2/2 known-bad cases caught = 100% Chinese fidelity recall.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.eval.golden_loader import GoldenCase, load_golden_cases
from app.eval.runner import CaseResult, EvalRunner

_SPEC_DIR = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "026-agent-eval-loop"
)

# Load all golden cases once at module import (cheap — file IO + JSON parse).
_ALL_CASES: list[GoldenCase] = load_golden_cases(_SPEC_DIR)
assert len(_ALL_CASES) == 10, (
    f"expected 10 golden cases, got {len(_ALL_CASES)}; "
    f"check specs/026-agent-eval-loop/golden/ contents"
)

# Single runner instance — stateless across cases, safe to reuse.
_RUNNER = EvalRunner(cases=_ALL_CASES, mode="mock")


def _case_id(case: GoldenCase) -> str:
    return case.case_id


@pytest.mark.parametrize("case", _ALL_CASES, ids=_case_id)
@pytest.mark.asyncio
async def test_golden_case_passes_eval_gate(case: GoldenCase) -> None:
    """Each golden case must pass the eval gate.

    For normal cases (expected_fidelity_pass=True): the LLM output must be
    Chinese-dominant, contain expected keywords, and match the score range.

    For regression cases (expected_fidelity_pass=False): the checker MUST
    flag the English output — if it doesn't, the case fails with
    `checker_failed_to_flag_expected_regression` (this is the SC-003 check).
    """
    result: CaseResult = await _RUNNER.run_case(case)
    assert result.passed is True, (
        f"case {case.case_id} ({case.node}) failed; "
        f"label={case.label}; "
        f"failure_reasons={result.failure_reasons}; "
        f"metrics={result.metrics}; "
        f"actual_output={result.actual_output}"
    )


class TestSC003ChineseFidelityRecall:
    """SC-003: Chinese fidelity metric must catch known-bad regression cases.

    Spec SC-003: "A known Chinese-fidelity regression case (zh-CN prompt
    producing English output) is automatically detected by the language
    fidelity metric with ≥95% recall."

    We have 2 known-bad cases (1 score + 1 report). Both must be flagged by
    the checker. 2/2 = 100% recall — exceeds the 95% threshold.
    """

    @pytest.mark.asyncio
    async def test_both_regression_cases_caught_by_checker(self) -> None:
        regression_cases = [c for c in _ALL_CASES if not c.expected_fidelity_pass]
        assert len(regression_cases) == 2, (
            f"expected 2 regression cases; got {len(regression_cases)}"
        )
        for case in regression_cases:
            result = await _RUNNER.run_case(case)
            assert result.passed is True, (
                f"regression case {case.case_id} should pass "
                f"(checker correctly flags English output); "
                f"failures={result.failure_reasons}"
            )
            assert result.metrics["chinese_fidelity"] < 0.3, (
                f"checker should give low fidelity score to English output; "
                f"got {result.metrics['chinese_fidelity']}"
            )


class TestEvalSuiteAggregateReport:
    """Validate aggregate EvalReport shape and content."""

    @pytest.mark.asyncio
    async def test_full_suite_run_returns_valid_report(self) -> None:
        report = await _RUNNER.run_all()
        assert report.total_cases == 10
        assert report.passed_cases == 10
        assert report.failed_cases == 0
        assert report.model == "mock-llm"
        assert report.git_sha, "git_sha must be non-empty"
        assert "interview.score" in report.per_node
        assert "interview.report" in report.per_node
        assert report.per_node["interview.score"]["total"] == 5.0
        assert report.per_node["interview.report"]["total"] == 5.0
        assert report.per_node["interview.score"]["pass_rate"] == 1.0
        assert report.per_node["interview.report"]["pass_rate"] == 1.0
