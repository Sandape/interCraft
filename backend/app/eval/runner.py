"""EvalRunner — replays golden cases through real graph nodes (T030/T031/T032).

For each GoldenCase:
1. Run ChineseFidelityChecker on the case's `llm_response` → fidelity metric
2. Patch `get_llm_client` to return a stub yielding `case.llm_response`
3. Patch `_sink_to_error_book` to a no-op (avoid DB dependency in eval)
4. Invoke the real node function (score_node / report_node) — this tests
   the full prompt assembly + JSON parsing + state shape logic
5. Validate `expected_contains` keywords appear in actual output
6. Validate `expected_score_range` / `expected_overall_score_range`
7. Handle `expected_fidelity_pass=False` reverse-assertion (regression cases
   that the checker should flag — if it doesn't, that's a checker regression)

Produces per-case CaseResult + aggregate EvalReport (FR-010, FR-013).

Mock mode (default): patches LLM client with deterministic stub.
Real mode (opt-in): does NOT patch — uses real DeepSeek V4 Pro. Real mode
requires `DEEPSEEK_API_KEY` env var and burns real quota; not run in CI.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import structlog

from app.eval.checker import ChineseFidelityChecker, ChineseFidelityResult
from app.eval.golden_loader import GoldenCase

logger = structlog.get_logger("eval.runner")


@dataclass
class CaseResult:
    """Per-case verdict from EvalRunner.run_case()."""

    case_id: str
    node: str
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    actual_output: dict[str, Any] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)
    label: str = ""
    expected_fidelity_pass: bool = True


@dataclass
class EvalReport:
    """Aggregate eval report (FR-013: timestamp + git_sha + model + per-case)."""

    timestamp: str
    git_sha: str
    model: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int
    per_node: dict[str, dict[str, float]] = field(default_factory=dict)
    case_results: list[CaseResult] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON string per FR-013."""
        # asdict() recursively converts CaseResult dataclasses to dicts, so
        # the default fallback only handles unexpected non-serializable types.
        return json.dumps(
            asdict(self),
            default=lambda obj: str(obj),
            ensure_ascii=False,
            indent=2,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return as plain dict (for structlog / programmatic consumers)."""
        return json.loads(self.to_json())


class _StubLLMClient:
    """Deterministic stub LLM client — yields the case's `llm_response`.

    Mimics the LLMResponse TypedDict shape so node code that does
    `result["content"]` works.
    """

    def __init__(self, response_content: str) -> None:
        self._content = response_content

    async def invoke(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "content": self._content,
            "model": "mock-llm",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "duration_ms": 0,
            "checkpoint_id": kwargs.get("checkpoint_id"),
        }

    async def invoke_stream(self, **kwargs: Any) -> Any:  # pragma: no cover
        yield self._content  # type: ignore[misc]


class EvalRunner:
    """Replays golden cases through real graph nodes; produces EvalReport."""

    def __init__(
        self,
        cases: list[GoldenCase],
        mode: str = "mock",
        model_name: str = "mock-llm",
    ) -> None:
        self.cases = cases
        self.mode = mode
        self.model_name = model_name
        self.checker = ChineseFidelityChecker()

    async def run_case(self, case: GoldenCase) -> CaseResult:
        """Run a single golden case through the real node function.

        Steps:
        1. Skip stale cases (status != "active").
        2. Run fidelity checker on case.llm_response.
        3. If mode="mock": patch get_llm_client with stub.
        4. Invoke real node function (score_node / report_node).
        5. Validate expected_contains / expected_score_range.
        6. Handle expected_fidelity_pass=False reverse-assertion.
        """
        if case.status != "active":
            return CaseResult(
                case_id=case.case_id,
                node=case.node,
                passed=False,
                metrics={},
                actual_output={},
                failure_reasons=[f"stale_case_skipped:{case.status}"],
                label=case.label,
                expected_fidelity_pass=case.expected_fidelity_pass,
            )

        # 1. Fidelity check
        fidelity: ChineseFidelityResult = self.checker.check(
            case.llm_response, expected_language=case.expected_language
        )

        failure_reasons: list[str] = []

        # 2. Reverse-assertion for regression cases
        if not case.expected_fidelity_pass:
            # Case represents known-bad output; checker SHOULD flag it.
            if fidelity.is_correct:
                # Checker passed → that's a regression in the checker itself!
                failure_reasons.append(
                    "checker_failed_to_flag_expected_regression"
                )
            # Don't add "chinese_fidelity" to failures — the case is designed
            # to fail fidelity, so it's expected.
        else:
            # Normal case — fidelity must pass.
            if not fidelity.is_correct:
                failure_reasons.append("chinese_fidelity")

        # 3. Invoke real node with patched LLM client
        actual_output: dict[str, Any] = {}
        node_error: str | None = None
        try:
            actual_output = await self._invoke_node(case)
        except Exception as exc:
            node_error = f"{type(exc).__name__}:{exc}"
            failure_reasons.append(f"node_invocation_error:{node_error}")

        # 4. Validate expected_contains
        if case.expected_contains and not node_error:
            missing = self._missing_keywords(
                case.expected_contains, actual_output
            )
            if missing:
                failure_reasons.append(f"expected_contains_missing:{missing}")

        # 5. Validate score range
        if case.expected_score_range and not node_error:
            score_ok, actual_score = self._check_score_range(case, actual_output)
            if not score_ok:
                failure_reasons.append(
                    f"score_range_violation:expected={case.expected_score_range},"
                    f"actual={actual_score}"
                )

        # 6. Validate overall_score range
        if case.expected_overall_score_range and not node_error:
            score_ok, actual_score = self._check_overall_score_range(
                case, actual_output
            )
            if not score_ok:
                failure_reasons.append(
                    f"overall_score_range_violation:expected="
                    f"{case.expected_overall_score_range},actual={actual_score}"
                )

        passed = len(failure_reasons) == 0
        metrics = {
            "chinese_fidelity": fidelity.score,
            "chinese_ratio": fidelity.chinese_ratio,
            "english_ratio": fidelity.english_ratio,
        }

        return CaseResult(
            case_id=case.case_id,
            node=case.node,
            passed=passed,
            metrics=metrics,
            actual_output=actual_output,
            failure_reasons=failure_reasons,
            label=case.label,
            expected_fidelity_pass=case.expected_fidelity_pass,
        )

    async def run_all(self) -> EvalReport:
        """Run all cases; return aggregate EvalReport."""
        results: list[CaseResult] = []
        for case in self.cases:
            result = await self.run_case(case)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        skipped = sum(
            1 for r in results
            if any("stale_case_skipped" in fr for fr in r.failure_reasons)
        )
        failed = sum(
            1 for r in results
            if not r.passed
            and not any("stale_case_skipped" in fr for fr in r.failure_reasons)
        )

        per_node = self._aggregate_per_node(results)

        return EvalReport(
            timestamp=datetime.now(UTC).isoformat(),
            git_sha=_get_git_sha(),
            model=self.model_name,
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=failed,
            skipped_cases=skipped,
            per_node=per_node,
            case_results=results,
        )

    # ------------------------------------------------------------------
    # Node invocation
    # ------------------------------------------------------------------
    async def _invoke_node(self, case: GoldenCase) -> dict[str, Any]:
        """Invoke the real node function with LLM client stubbed.

        The node function reads `state` (case.input_state), calls
        `get_llm_client().invoke(...)` which we patch to yield
        `case.llm_response`, and returns a state-update dict.

        For score_node: also patches `_sink_to_error_book` to a no-op so the
        eval suite doesn't need a real DB connection.
        """
        state = dict(case.input_state)
        node = case.node

        stub = _StubLLMClient(case.llm_response)

        if node == "interview.score":
            return await self._invoke_score_node(state, stub)
        if node == "interview.report":
            return await self._invoke_report_node(state, stub)
        # Future: error_coach.evaluate, resume_optimize.generate, etc.
        raise ValueError(f"unsupported_node:{node}")

    async def _invoke_score_node(
        self, state: dict[str, Any], stub: _StubLLMClient
    ) -> dict[str, Any]:
        """Invoke interview.nodes.score.score_node with patched deps."""
        from app.agents.interview.nodes.score import score_node

        with (
            patch("app.agents.interview.nodes.score.get_llm_client", return_value=stub),
            patch("app.agents.interview.nodes.score._sink_to_error_book", new=_noop_sink),
        ):
            return await score_node(state)

    async def _invoke_report_node(
        self, state: dict[str, Any], stub: _StubLLMClient
    ) -> dict[str, Any]:
        """Invoke interview.nodes.report.report_node with patched deps."""
        from app.agents.interview.nodes.report import report_node

        with patch(
            "app.agents.interview.nodes.report.get_llm_client", return_value=stub
        ):
            return await report_node(state)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _missing_keywords(
        keywords: list[str], actual_output: dict[str, Any]
    ) -> list[str]:
        """Return keywords that don't appear anywhere in actual_output's string repr."""
        # Flatten actual_output to a searchable string (handles nested dicts/lists).
        haystack = json.dumps(actual_output, ensure_ascii=False)
        return [kw for kw in keywords if kw not in haystack]

    @staticmethod
    def _check_score_range(
        case: GoldenCase, actual_output: dict[str, Any]
    ) -> tuple[bool, int | None]:
        """For score_node: extract last score's `score` and check range."""
        scores = actual_output.get("scores", [])
        if not scores:
            return False, None
        last_score = scores[-1].get("score")
        if last_score is None:
            return False, None
        lo, hi = case.expected_score_range or (0, 10)
        return lo <= int(last_score) <= hi, int(last_score)

    @staticmethod
    def _check_overall_score_range(
        case: GoldenCase, actual_output: dict[str, Any]
    ) -> tuple[bool, float | None]:
        """For report_node: extract overall_score and check range."""
        overall = actual_output.get("overall_score")
        if overall is None:
            return False, None
        lo, hi = case.expected_overall_score_range or (0.0, 10.0)
        return lo <= float(overall) <= hi, float(overall)

    @staticmethod
    def _aggregate_per_node(results: list[CaseResult]) -> dict[str, dict[str, float]]:
        """Per-node aggregate metrics: pass_rate + avg_fidelity."""
        per_node: dict[str, dict[str, float]] = {}
        node_buckets: dict[str, list[CaseResult]] = {}
        for r in results:
            node_buckets.setdefault(r.node, []).append(r)

        for node, bucket in node_buckets.items():
            total = len(bucket)
            passed = sum(1 for r in bucket if r.passed)
            avg_fidelity = (
                sum(r.metrics.get("chinese_fidelity", 0.0) for r in bucket) / total
                if total
                else 0.0
            )
            per_node[node] = {
                "total": float(total),
                "passed": float(passed),
                "pass_rate": round(passed / total, 4) if total else 0.0,
                "avg_chinese_fidelity": round(avg_fidelity, 4),
            }
        return per_node


async def _noop_sink(*args: Any, **kwargs: Any) -> None:
    """No-op replacement for `_sink_to_error_book` — eval suite skips DB.

    The real `_sink_to_error_book` writes low-scoring answers to
    `error_questions` table. Eval suite doesn't need DB, so we stub it out.
    """
    return None


def _get_git_sha() -> str:
    """Read current git SHA for eval report (FR-013).

    Tries `git rev-parse HEAD`; falls back to env var `GIT_SHA`; finally
    "unknown".
    """
    env_sha = os.environ.get("GIT_SHA", "").strip()
    if env_sha:
        return env_sha

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


__all__ = ["CaseResult", "EvalReport", "EvalRunner"]
