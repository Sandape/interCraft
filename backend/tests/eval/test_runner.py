"""EvalRunner unit tests (Phase 4 TDD).

Validates the runner that replays golden cases through real node functions
(with LLM client stubbed). Tests both per-case `run_case()` and aggregate
`run_all()` paths.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.golden_loader import GoldenCase
from app.eval.runner import EvalReport, EvalRunner

_SPEC_DIR = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "026-agent-eval-loop"
)


def _make_case(
    case_id: str = "test_case",
    node: str = "interview.score",
    llm_response: str = '{"score": 9, "dimension": "tech_depth", "feedback": "候选人对 React diff 算法理解深入。", "sub_scores": {"clarity": 9, "depth": 9, "relevance": 9}}',
    expected_fidelity_pass: bool = True,
    expected_score_range: tuple[int, int] | None = (9, 10),
    expected_contains: list[str] | None = None,
    input_state: dict | None = None,
) -> GoldenCase:
    if input_state is None:
        input_state = {
            "questions": [{"question": "解释 React diff", "dimension": "tech_depth"}],
            "scores": [],
            "current_question": 0,
            "messages": [{"role": "user", "content": "test answer"}],
            "difficulty": "medium",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "thread_id": "00000000-0000-0000-0000-000000000002",
        }
    return GoldenCase(
        case_id=case_id,
        node=node,
        label="test case",
        source="manual",
        input_state=input_state,
        llm_response=llm_response,
        expected_language="zh-CN",
        expected_contains=expected_contains or [],
        expected_score_range=expected_score_range,
        expected_overall_score_range=None,
        expected_fidelity_pass=expected_fidelity_pass,
        status="active",
    )


@pytest.fixture
def runner() -> EvalRunner:
    return EvalRunner(cases=[], mode="mock")


class TestRunCaseSingle:
    """Tests for EvalRunner.run_case() on a single case."""

    @pytest.mark.asyncio
    async def test_run_case_pure_chinese_passes(self, runner: EvalRunner) -> None:
        case = _make_case()
        result = await runner.run_case(case)
        assert result.passed is True, (
            f"pure Chinese case should pass; failures={result.failure_reasons}"
        )
        assert result.case_id == "test_case"
        assert result.node == "interview.score"
        assert "chinese_fidelity" in result.metrics
        assert result.metrics["chinese_fidelity"] > 0.3

    @pytest.mark.asyncio
    async def test_run_case_english_regression_fails(
        self, runner: EvalRunner
    ) -> None:
        """English feedback + expected_fidelity_pass=True → checker flags it → fail."""
        english_llm = (
            '{"score": 8, "dimension": "tech_depth", '
            '"feedback": "The candidate demonstrated solid understanding of React.", '
            '"sub_scores": {"clarity": 8, "depth": 8, "relevance": 8}}'
        )
        case = _make_case(
            llm_response=english_llm,
            expected_fidelity_pass=True,
            expected_score_range=(8, 8),
        )
        result = await runner.run_case(case)
        assert result.passed is False
        assert "chinese_fidelity" in result.failure_reasons

    @pytest.mark.asyncio
    async def test_run_case_expected_fidelity_pass_false_regression_caught(
        self, runner: EvalRunner
    ) -> None:
        """expected_fidelity_pass=False + English output → checker should catch → passed=True.

        This validates SC-003: the checker correctly flags the known-bad
        regression case. If the checker missed it, the case would fail with
        `checker_failed_to_flag_expected_regression`.
        """
        english_llm = (
            '{"score": 8, "dimension": "tech_depth", '
            '"feedback": "The candidate demonstrated solid understanding of React.", '
            '"sub_scores": {"clarity": 8, "depth": 8, "relevance": 8}}'
        )
        case = _make_case(
            llm_response=english_llm,
            expected_fidelity_pass=False,
            expected_score_range=(8, 8),
        )
        result = await runner.run_case(case)
        assert result.passed is True, (
            f"regression case with expected_fidelity_pass=False should pass "
            f"(checker caught it); failures={result.failure_reasons}"
        )

    @pytest.mark.asyncio
    async def test_run_case_expected_fidelity_pass_false_but_checker_missed(
        self, runner: EvalRunner
    ) -> None:
        """If expected_fidelity_pass=False but LLM output is actually Chinese,
        the checker doesn't flag it → case fails with `checker_failed_to_flag_expected_regression`.

        This is a meta-test: it validates the reverse-assertion logic works.
        If someone mistakenly labels a passing case as `expected_fidelity_pass=false`,
        the eval suite should fail (catch the mislabeling).
        """
        chinese_llm = (
            '{"score": 9, "dimension": "tech_depth", '
            '"feedback": "候选人对 React diff 算法理解深入。"}'
        )
        case = _make_case(
            llm_response=chinese_llm,
            expected_fidelity_pass=False,
            expected_score_range=(9, 9),
        )
        result = await runner.run_case(case)
        assert result.passed is False
        assert "checker_failed_to_flag_expected_regression" in result.failure_reasons

    @pytest.mark.asyncio
    async def test_run_case_score_range_violation(
        self, runner: EvalRunner
    ) -> None:
        """Expected score 9-10, actual 5 → fail with score_range_violation."""
        low_score_llm = (
            '{"score": 5, "dimension": "tech_depth", '
            '"feedback": "候选人理解一般，建议加强学习。"}'
        )
        case = _make_case(
            llm_response=low_score_llm,
            expected_score_range=(9, 10),
        )
        result = await runner.run_case(case)
        assert result.passed is False
        assert any("score_range_violation" in r for r in result.failure_reasons), (
            f"expected score_range_violation; got {result.failure_reasons}"
        )

    @pytest.mark.asyncio
    async def test_run_case_expected_contains_missing(
        self, runner: EvalRunner
    ) -> None:
        """expected_contains=['TypeScript'] but LLM output has no TS keyword → fail."""
        case = _make_case(
            expected_contains=["TypeScript"],  # not in test LLM response
        )
        result = await runner.run_case(case)
        assert result.passed is False
        assert any("expected_contains_missing" in r for r in result.failure_reasons)

    @pytest.mark.asyncio
    async def test_run_case_stale_case_skipped(self, runner: EvalRunner) -> None:
        """status="stale" case → skipped, not run."""
        case = _make_case()
        case.status = "stale"
        result = await runner.run_case(case)
        assert result.passed is False
        assert any("stale_case_skipped" in r for r in result.failure_reasons)


class TestRunAllAggregate:
    """Tests for EvalRunner.run_all() aggregate report."""

    @pytest.mark.asyncio
    async def test_run_all_returns_eval_report(self, runner: EvalRunner) -> None:
        runner.cases = [_make_case("case_a"), _make_case("case_b")]
        report = await runner.run_all()
        assert isinstance(report, EvalReport)
        assert report.total_cases == 2
        assert report.passed_cases == 2
        assert report.failed_cases == 0
        assert report.skipped_cases == 0

    @pytest.mark.asyncio
    async def test_run_all_counts_failed_cases(self, runner: EvalRunner) -> None:
        good = _make_case("good", expected_score_range=(9, 10))
        bad = _make_case(
            "bad",
            llm_response='{"score": 5, "dimension": "tech_depth", "feedback": "候选人理解一般。"}',
            expected_score_range=(9, 10),
        )
        runner.cases = [good, bad]
        report = await runner.run_all()
        assert report.total_cases == 2
        assert report.passed_cases == 1
        assert report.failed_cases == 1

    @pytest.mark.asyncio
    async def test_run_all_skips_stale_cases(self, runner: EvalRunner) -> None:
        good = _make_case("good")
        stale = _make_case("stale")
        stale.status = "stale"
        runner.cases = [good, stale]
        report = await runner.run_all()
        assert report.total_cases == 2
        assert report.passed_cases == 1
        assert report.skipped_cases == 1

    @pytest.mark.asyncio
    async def test_run_all_per_node_aggregation(
        self, runner: EvalRunner
    ) -> None:
        runner.cases = [
            _make_case("s1", node="interview.score"),
            _make_case("s2", node="interview.score"),
        ]
        report = await runner.run_all()
        assert "interview.score" in report.per_node
        node_stats = report.per_node["interview.score"]
        assert node_stats["total"] == 2.0
        assert node_stats["passed"] == 2.0
        assert node_stats["pass_rate"] == 1.0


class TestEvalReportSerialization:
    """FR-013: report must serialize to JSON with timestamp + git_sha + model."""

    @pytest.mark.asyncio
    async def test_eval_report_contains_git_sha_and_model(
        self, runner: EvalRunner
    ) -> None:
        runner.cases = [_make_case()]
        report = await runner.run_all()
        assert report.git_sha, "git_sha must be non-empty"
        assert report.model == "mock-llm"
        assert report.timestamp  # ISO string

    @pytest.mark.asyncio
    async def test_eval_report_to_json_serializable(
        self, runner: EvalRunner
    ) -> None:
        runner.cases = [_make_case()]
        report = await runner.run_all()
        json_str = report.to_json()
        assert isinstance(json_str, str)
        # Round-trip: must be valid JSON
        parsed = json.loads(json_str)
        assert parsed["total_cases"] == 1
        assert parsed["model"] == "mock-llm"
        assert "timestamp" in parsed
        assert "git_sha" in parsed
        assert "case_results" in parsed
        assert len(parsed["case_results"]) == 1

    @pytest.mark.asyncio
    async def test_eval_report_to_dict_returns_dict(
        self, runner: EvalRunner
    ) -> None:
        runner.cases = [_make_case()]
        report = await runner.run_all()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["total_cases"] == 1


class TestRunRealGoldenCases:
    """Smoke test: load the real 10 cases and run them."""

    @pytest.mark.asyncio
    async def test_run_real_cases_9_pass_1_expected_fail(
        self, runner: EvalRunner
    ) -> None:
        """Run all 10 real golden cases through the runner.

        Expected:
        - 8 normal cases (4 score + 4 report) → pass
        - 2 regression cases (1 score + 1 report, expected_fidelity_pass=False)
          → pass too (checker correctly flags them)
        - Total: 10 pass, 0 fail
        """
        from app.eval.golden_loader import load_golden_cases
        cases = load_golden_cases(_SPEC_DIR)
        runner.cases = cases
        report = await runner.run_all()
        assert report.total_cases == 10
        assert report.passed_cases == 10, (
            f"expected 10 passed (8 normal + 2 regression caught); "
            f"got passed={report.passed_cases}, failed={report.failed_cases}; "
            f"failures: {[r.failure_reasons for r in report.case_results if not r.passed]}"
        )
        assert report.failed_cases == 0
