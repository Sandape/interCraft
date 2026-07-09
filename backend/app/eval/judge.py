"""Deterministic judge helpers for REQ-045 US4.

The production LLM-as-Judge adapter can plug in later; this module locks the
calibration and reporting contract without requiring network calls.
"""
from __future__ import annotations

from typing import Any

from app.eval.schemas import JudgeCalibrationStatus, JudgeRubricRecord


def default_judge_rubric(
    *,
    owner: str,
    version: str = "rubric.req045.v1",
    judge_model: str = "mock-judge",
) -> JudgeRubricRecord:
    return JudgeRubricRecord(
        name="REQ-045 task quality judge",
        version=version,
        dimensions=["task_success", "fidelity", "safety"],
        scale={"min": 0.0, "max": 1.0, "blocking_threshold": 0.8},
        judge_model=judge_model,
        calibration_status=JudgeCalibrationStatus.REPORT_ONLY,
        owner=owner,
    )


def _label_bool(row: dict[str, Any], key: str) -> bool:
    return bool(row.get(key) if key in row else row.get(key.replace("_", "")))


def calibrate_judge_rubric(
    labels: list[dict[str, Any]],
    *,
    owner: str,
    min_labels: int = 30,
    agreement_threshold: float = 0.8,
    waiver_reason: str | None = None,
) -> JudgeRubricRecord:
    total = len(labels)
    matches = sum(
        1
        for row in labels
        if _label_bool(row, "human_passed") == _label_bool(row, "judge_passed")
    )
    agreement = (matches / total) if total else 0.0
    calibrated = total >= min_labels and agreement >= agreement_threshold
    status = (
        JudgeCalibrationStatus.BLOCKING_ENABLED
        if calibrated or waiver_reason
        else JudgeCalibrationStatus.REPORT_ONLY
    )
    return JudgeRubricRecord(
        name="REQ-045 task quality judge",
        version="rubric.req045.v1",
        dimensions=["task_success", "fidelity", "safety"],
        scale={
            "min": 0.0,
            "max": 1.0,
            "blocking_threshold": agreement_threshold,
            "min_labels": min_labels,
        },
        judge_model="mock-judge",
        calibration_status=status,
        human_label_count=total,
        agreement_rate=round(agreement, 4),
        owner=owner,
        waiver_reason=waiver_reason,
    )


def _case_score(case: dict[str, Any]) -> float:
    metrics = case.get("deterministicMetrics") or case.get("deterministic_metrics") or {}
    if "score" in metrics:
        return float(metrics["score"])
    if "judgeScore" in case:
        return float(case["judgeScore"])
    return 1.0 if bool(case.get("passed")) else 0.0


def run_judge_cases(
    cases: list[dict[str, Any]],
    *,
    rubric: JudgeRubricRecord | None = None,
) -> dict[str, Any]:
    rubric = rubric or default_judge_rubric(owner="ai-ops")
    threshold = float(rubric.scale.get("blocking_threshold", 0.8))
    blocking_enabled = rubric.calibration_status == JudgeCalibrationStatus.BLOCKING_ENABLED
    verdicts: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        score = max(0.0, min(1.0, _case_score(case)))
        passed = score >= threshold
        case_id = str(case.get("caseId") or case.get("case_id") or f"case-{index + 1}")
        verdicts.append(
            {
                "judgeVerdictId": f"judge-{case_id}",
                "caseId": case_id,
                "score": round(score, 4),
                "passed": passed,
                "rationale": "deterministic mock judge score from case metrics",
                "blocksMerge": bool(blocking_enabled and not passed),
                "rubricVersion": rubric.version,
                "calibrationStatus": rubric.calibration_status.value,
            }
        )
    return {
        "rubricId": rubric.rubric_id,
        "rubricVersion": rubric.version,
        "calibrationStatus": rubric.calibration_status.value,
        "blockingEnabled": blocking_enabled,
        "verdicts": verdicts,
    }


__all__ = [
    "calibrate_judge_rubric",
    "default_judge_rubric",
    "run_judge_cases",
]
