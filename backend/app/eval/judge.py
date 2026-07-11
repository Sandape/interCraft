"""Deterministic judge helpers for REQ-045 US4 + REQ-061 US11 (T146).

The production LLM-as-Judge adapter can plug in later; this module locks the
calibration and reporting contract without requiring network calls.

REQ-061 additions keep the REQ-045 API stable and add versioned execution,
report-only/blocking eligibility, and human comparison hooks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

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


# ---------------------------------------------------------------------------
# REQ-061 US11 interfaces
# ---------------------------------------------------------------------------

REQ061_JUDGE_VERSION = "judge.req061.v1"


@dataclass
class JudgeVerdict061:
    """Versioned single-case judge result (FR-145)."""

    judge_verdict_id: str
    case_id: str
    score: float
    passed: bool
    rationale: str
    rubric_version: str
    judge_model: str
    judge_version: str
    calibration_status: str
    blocks_release: bool
    evidence_range: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "judge_verdict_id": self.judge_verdict_id,
            "case_id": self.case_id,
            "score": self.score,
            "passed": self.passed,
            "rationale": self.rationale,
            "rubric_version": self.rubric_version,
            "judge_model": self.judge_model,
            "judge_version": self.judge_version,
            "calibration_status": self.calibration_status,
            "blocks_release": self.blocks_release,
            "evidence_range": dict(self.evidence_range),
            "evaluated_at": self.evaluated_at,
        }


def default_req061_rubric(
    *,
    owner: str = "ai-quality",
    version: str = "rubric.req061.v1",
    judge_model: str = "mock-judge",
    calibration_status: JudgeCalibrationStatus = JudgeCalibrationStatus.REPORT_ONLY,
) -> JudgeRubricRecord:
    return JudgeRubricRecord(
        name="REQ-061 production quality judge",
        version=version,
        dimensions=["task_success", "fidelity", "safety", "factuality"],
        scale={
            "min": 0.0,
            "max": 1.0,
            "blocking_threshold": 0.85,
            "min_labels": 100,
        },
        judge_model=judge_model,
        calibration_status=calibration_status,
        owner=owner,
    )


def is_blocking_eligible(rubric: JudgeRubricRecord) -> bool:
    """True only when calibration permits blocking release gates (FR-146)."""
    return rubric.calibration_status == JudgeCalibrationStatus.BLOCKING_ENABLED


def evaluate_case(
    case: dict[str, Any],
    *,
    rubric: JudgeRubricRecord | None = None,
    judge_version: str = REQ061_JUDGE_VERSION,
) -> JudgeVerdict061:
    """Run versioned judge on one case (deterministic mock path)."""
    rubric = rubric or default_req061_rubric()
    threshold = float(rubric.scale.get("blocking_threshold", 0.85))
    score = max(0.0, min(1.0, _case_score(case)))
    passed = score >= threshold
    case_id = str(case.get("caseId") or case.get("case_id") or uuid4())
    blocking = is_blocking_eligible(rubric) and not passed
    return JudgeVerdict061(
        judge_verdict_id=f"judge-{case_id}",
        case_id=case_id,
        score=round(score, 4),
        passed=passed,
        rationale="deterministic REQ-061 mock judge score from case metrics",
        rubric_version=rubric.version,
        judge_model=rubric.judge_model,
        judge_version=judge_version,
        calibration_status=rubric.calibration_status.value,
        blocks_release=blocking,
        evidence_range={
            "input_keys": sorted(
                k for k in case.keys() if k not in {"llm_response", "raw"}
            ),
        },
    )


def compare_with_human(
    verdict: JudgeVerdict061,
    *,
    human_passed: bool,
    human_severity: str | None = None,
) -> dict[str, Any]:
    """Compare automatic verdict with a human label (FR-146)."""
    agree = verdict.passed == human_passed
    p0_p1_miss = (
        (human_severity or "").upper() in {"P0", "P1"}
        and (not human_passed)
        and verdict.passed
    )
    return {
        "case_id": verdict.case_id,
        "agree": agree,
        "p0_p1_miss": p0_p1_miss,
        "judge_passed": verdict.passed,
        "human_passed": human_passed,
        "human_severity": human_severity,
        "judge_version": verdict.judge_version,
        "rubric_version": verdict.rubric_version,
    }


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
    "JudgeVerdict061",
    "REQ061_JUDGE_VERSION",
    "calibrate_judge_rubric",
    "compare_with_human",
    "default_judge_rubric",
    "default_req061_rubric",
    "evaluate_case",
    "is_blocking_eligible",
    "run_judge_cases",
]
