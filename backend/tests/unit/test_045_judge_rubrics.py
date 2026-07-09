from __future__ import annotations

import pytest

from app.eval.judge import calibrate_judge_rubric, default_judge_rubric, run_judge_cases
from app.eval.schemas import JudgeCalibrationStatus, JudgeRubricRecord


def test_default_judge_rubric_is_report_only() -> None:
    rubric = default_judge_rubric(owner="ai-ops")

    assert rubric.calibration_status == JudgeCalibrationStatus.REPORT_ONLY
    assert rubric.dimensions == ["task_success", "fidelity", "safety"]


def test_blocking_rubric_requires_calibration_or_waiver() -> None:
    with pytest.raises(ValueError, match="requires calibration or waiver"):
        JudgeRubricRecord(
            name="bad",
            version="v1",
            dimensions=["task_success"],
            scale={"min": 0, "max": 1},
            judge_model="mock-judge",
            calibration_status=JudgeCalibrationStatus.BLOCKING_ENABLED,
            human_label_count=10,
            agreement_rate=0.5,
            owner="ai-ops",
        )


def test_calibration_enables_blocking_above_threshold() -> None:
    labels = [{"human_passed": True, "judge_passed": True} for _ in range(30)]

    rubric = calibrate_judge_rubric(labels, owner="ai-ops")

    assert rubric.calibration_status == JudgeCalibrationStatus.BLOCKING_ENABLED
    assert rubric.human_label_count == 30
    assert rubric.agreement_rate == 1.0


def test_waiver_allows_blocking_without_threshold() -> None:
    labels = [{"human_passed": True, "judge_passed": False} for _ in range(5)]

    rubric = calibrate_judge_rubric(
        labels,
        owner="ai-ops",
        waiver_reason="temporary PM-approved rollout",
    )

    assert rubric.calibration_status == JudgeCalibrationStatus.BLOCKING_ENABLED
    assert rubric.waiver_reason == "temporary PM-approved rollout"


def test_report_only_judge_never_blocks_merge() -> None:
    rubric = default_judge_rubric(owner="ai-ops")
    result = run_judge_cases(
        [{"caseId": "case-1", "passed": False, "deterministicMetrics": {"score": 0.2}}],
        rubric=rubric,
    )

    assert result["blockingEnabled"] is False
    assert result["verdicts"][0]["blocksMerge"] is False
