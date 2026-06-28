"""REQ-033 US9 — Eval runner version-field tests (T035).

Locks the data-model.md §EvalRun contract:

- ``EvalReport`` carries a ``version_context`` (``VersionContext``) attribute.
- Aggregate fields exist on the report: ``aggregate_pass_rate``,
  ``known_regression_recall``, ``stale_case_count``.
- Prompt fingerprint is auto-derived from prompt if a fingerprint is
  available; otherwise explicit ``"unknown"`` (SC-010).
- Model + rubric version surface as part of the version context.
- Missing version context fields default to ``"unknown"`` — never None /
  empty / omitted.

All tests are TDD — they MUST fail before T037/T038 implementations land.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from app.eval.golden_loader import GoldenCase
from app.eval.runner import EvalReport, EvalRunner, run_eval_suite

_SPEC_DIR = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "026-agent-eval-loop"
)


def _make_case(
    case_id: str = "us9_case",
    node: str = "interview.score",
    llm_response: str = '{"score": 9, "dimension": "tech_depth", "feedback": "候选人对 React diff 算法理解深入。", "sub_scores": {"clarity": 9, "depth": 9, "relevance": 9}}',
) -> GoldenCase:
    return GoldenCase(
        case_id=case_id,
        node=node,
        label="us9 test case",
        source="manual",
        input_state={
            "questions": [{"question": "解释 React diff", "dimension": "tech_depth"}],
            "scores": [],
            "current_question": 0,
            "messages": [{"role": "user", "content": "test answer"}],
            "difficulty": "medium",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "thread_id": "00000000-0000-0000-0000-000000000002",
        },
        llm_response=llm_response,
        expected_language="zh-CN",
        expected_contains=[],
        expected_score_range=(9, 10),
        expected_fidelity_pass=True,
        status="active",
    )


# ---------------------------------------------------------------------------
# version_context on EvalReport
# ---------------------------------------------------------------------------


class TestEvalReportVersionContext:
    """EvalReport must carry a VersionContext (T038 extension)."""

    @pytest.mark.asyncio
    async def test_eval_report_has_version_context_attribute(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert hasattr(report, "version_context"), (
            "EvalReport must carry a version_context attribute (T038)"
        )
        vc = report.version_context
        assert vc is not None
        # Required fields exist and are non-empty.
        assert vc.app_version
        assert vc.release_stage
        assert vc.environment
        assert vc.schema_version

    @pytest.mark.asyncio
    async def test_version_context_uses_environment_param(self) -> None:
        """Environment passed to runner is reflected in VersionContext."""
        report = await run_eval_suite(
            cases=[_make_case()],
            mode="mock",
            model_name="mock-llm",
            environment="STAGING",
        )
        assert report.version_context.environment == "STAGING"

    @pytest.mark.asyncio
    async def test_version_context_default_environment(self) -> None:
        """Default environment should be one of the canonical enums."""
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert report.version_context.environment in {
            "LOCAL",
            "CI",
            "STAGING",
            "PRODUCTION",
        }

    @pytest.mark.asyncio
    async def test_version_context_release_stage_valid_enum(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert report.version_context.release_stage in {
            "DEVELOPMENT",
            "RELEASE_CANDIDATE",
            "PRODUCTION",
            "UNKNOWN",
        }


# ---------------------------------------------------------------------------
# Aggregate fields
# ---------------------------------------------------------------------------


class TestEvalReportAggregateFields:
    """Aggregate fields per data-model.md §EvalRun."""

    @pytest.mark.asyncio
    async def test_report_has_aggregate_pass_rate(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert hasattr(report, "aggregate_pass_rate"), (
            "EvalReport must carry aggregate_pass_rate (T038)"
        )
        apr = report.aggregate_pass_rate
        assert apr is not None
        assert 0.0 <= apr <= 1.0

    @pytest.mark.asyncio
    async def test_aggregate_pass_rate_with_passing_case(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        # 1/1 passes → 1.0
        assert report.aggregate_pass_rate == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_report_has_known_regression_recall(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert hasattr(report, "known_regression_recall"), (
            "EvalReport must carry known_regression_recall (T038)"
        )
        krr = report.known_regression_recall
        assert krr is not None
        assert 0.0 <= krr <= 1.0

    @pytest.mark.asyncio
    async def test_report_has_stale_case_count(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert hasattr(report, "stale_case_count"), (
            "EvalReport must carry stale_case_count (T038)"
        )
        scc = report.stale_case_count
        assert scc is not None
        assert scc >= 0

    @pytest.mark.asyncio
    async def test_report_has_source_revision(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert hasattr(report, "source_revision"), (
            "EvalReport must carry source_revision (T038)"
        )
        sr = report.source_revision
        assert sr is not None
        assert sr != ""  # Not empty (could be "unknown" if git missing)

    @pytest.mark.asyncio
    async def test_report_has_branch_field(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert hasattr(report, "branch"), (
            "EvalReport must carry branch (T038)"
        )
        br = report.branch
        assert br is not None


# ---------------------------------------------------------------------------
# Prompt fingerprint derivation
# ---------------------------------------------------------------------------


class TestPromptFingerprintDerivation:
    """Prompt fingerprint is auto-derived from prompt, or explicit ``"unknown"``."""

    @pytest.mark.asyncio
    async def test_version_context_prompt_fingerprint_non_empty(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        vc = report.version_context
        # Must be either a real fingerprint OR explicit "unknown" — never None/empty.
        assert vc.prompt_fingerprint is not None
        assert vc.prompt_fingerprint != ""

    @pytest.mark.asyncio
    async def test_prompt_fingerprint_deterministic(self) -> None:
        """Same prompt + config → same fingerprint across runs."""
        r1 = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        r2 = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        # Both reports get fresh fingerprints per run, BUT the fingerprint
        # value is derived deterministically from inputs. If model_name is
        # same and there's no random salt, the derived fingerprint should be
        # identical.
        # Allow either: (a) same fingerprint (deterministic) or (b) "unknown"
        # if config is missing. Both are spec-compliant.
        fp1 = r1.version_context.prompt_fingerprint
        fp2 = r2.version_context.prompt_fingerprint
        # No None / no empty ever.
        assert fp1 and fp2
        # Both are either identical (deterministic) or both "unknown" (no
        # source). A mix would be a bug.
        assert fp1 == fp2 or (fp1 == "unknown" and fp2 == "unknown")


# ---------------------------------------------------------------------------
# Model + rubric_version in version context
# ---------------------------------------------------------------------------


class TestModelAndRubricInVersionContext:
    """Model name + rubric version surface in VersionContext (T038)."""

    @pytest.mark.asyncio
    async def test_version_context_model_reflects_runner_model(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="deepseek-v4-pro"
        )
        assert report.version_context.model in (
            "deepseek-v4-pro",
            "unknown",
        )

    @pytest.mark.asyncio
    async def test_version_context_rubric_version_field_present(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        # Either a real rubric version OR explicit "unknown".
        rv = report.version_context.rubric_version
        assert rv is not None
        assert rv != ""

    @pytest.mark.asyncio
    async def test_rubric_version_override_propagates(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()],
            mode="mock",
            model_name="mock-llm",
            rubric_version="rubric-2026-06-26",
        )
        assert report.version_context.rubric_version == "rubric-2026-06-26"


# ---------------------------------------------------------------------------
# SC-010: missing → "unknown", never None
# ---------------------------------------------------------------------------


class TestEvalReportSC010Compliance:
    """All version fields are explicit (SC-010 / FR-038)."""

    @pytest.mark.asyncio
    async def test_version_context_no_none_fields(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        vc = report.version_context
        # Use the to_dict representation to check no None / empty.
        d = vc.to_dict()
        for k, v in d.items():
            assert v is not None, f"{k} is None (SC-010 violation)"
            assert v != "", f"{k} is empty (SC-010 violation)"

    @pytest.mark.asyncio
    async def test_to_json_includes_version_context(self) -> None:
        """JSON output of EvalReport includes the version context fields."""
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        import json

        payload = json.loads(report.to_json())
        # Either top-level fields or nested under version_context are both ok.
        # The contract is the value is present and is a string.
        # Some implementations flatten; the safer assertion: at least one
        # version-related key has a non-empty string.
        vc_keys = [
            "version_context",
            "versionContext",
            "prompt_fingerprint",
            "promptFingerprint",
        ]
        found = False
        for k in vc_keys:
            if k in payload and payload[k]:
                found = True
                break
        assert found, f"version context missing from JSON: keys={list(payload.keys())}"

    @pytest.mark.asyncio
    async def test_run_id_is_stable_uuid(self) -> None:
        report = await run_eval_suite(
            cases=[_make_case()], mode="mock", model_name="mock-llm"
        )
        assert isinstance(report.run_id, UUID)
