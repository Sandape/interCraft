"""REQ-061 US11 — evaluator calibration storage & eligibility (T146 / FR-146).

Monthly stratified human comparison (≥100 labels, ≥85% agreement,
zero P0/P1 misses). Below threshold → report-only; never blocking alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from app.eval.schemas import JudgeCalibrationStatus

MIN_MONTHLY_LABELS = 100
MIN_AGREEMENT_RATE = 0.85


class CalibrationEligibility(StrEnum):
    REPORT_ONLY = "report_only"
    BLOCKING_ELIGIBLE = "blocking_eligible"
    BLOCKING_DISABLED = "blocking_disabled"


@dataclass
class CalibrationExample:
    example_id: str
    capability_code: str
    stratum: str  # e.g. normal / boundary / failure / privacy / adversarial
    severity: str | None  # P0 / P1 / P2 / None
    human_passed: bool
    judge_passed: bool
    month: str  # YYYY-MM


@dataclass
class CalibrationReport:
    calibration_id: str
    month: str
    label_count: int
    agreement_rate: float
    p0_p1_misses: int
    eligibility: CalibrationEligibility
    status: JudgeCalibrationStatus
    strata_counts: dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration_id": self.calibration_id,
            "month": self.month,
            "label_count": self.label_count,
            "agreement_rate": self.agreement_rate,
            "p0_p1_misses": self.p0_p1_misses,
            "eligibility": self.eligibility.value,
            "status": self.status.value,
            "strata_counts": dict(self.strata_counts),
            "created_at": self.created_at,
            "notes": self.notes,
        }


class CalibrationStore:
    """In-memory calibration history (swap for DB later)."""

    def __init__(self) -> None:
        self._reports: dict[str, CalibrationReport] = {}
        self._examples: list[CalibrationExample] = []

    def add_examples(self, examples: list[CalibrationExample]) -> None:
        self._examples.extend(examples)

    def examples_for_month(self, month: str) -> list[CalibrationExample]:
        return [e for e in self._examples if e.month == month]

    def save(self, report: CalibrationReport) -> CalibrationReport:
        self._reports[report.calibration_id] = report
        return report

    def latest(self, month: str | None = None) -> CalibrationReport | None:
        reports = list(self._reports.values())
        if month:
            reports = [r for r in reports if r.month == month]
        if not reports:
            return None
        return sorted(reports, key=lambda r: r.created_at)[-1]

    def list_reports(self) -> list[CalibrationReport]:
        return list(self._reports.values())


def count_p0_p1_misses(examples: list[CalibrationExample]) -> int:
    """Miss = human flagged fail (or P0/P1) but judge passed."""
    misses = 0
    for ex in examples:
        sev = (ex.severity or "").upper()
        if sev in {"P0", "P1"} and (not ex.human_passed) and ex.judge_passed:
            misses += 1
        elif sev in {"P0", "P1"} and ex.human_passed is False and ex.judge_passed:
            misses += 1
    # Also count any P0/P1 where human_passed != judge_passed and human said fail.
    return misses


def compute_agreement(examples: list[CalibrationExample]) -> float:
    if not examples:
        return 0.0
    matches = sum(1 for e in examples if e.human_passed == e.judge_passed)
    return matches / len(examples)


def decide_eligibility(
    *,
    label_count: int,
    agreement_rate: float,
    p0_p1_misses: int,
) -> tuple[CalibrationEligibility, JudgeCalibrationStatus]:
    if (
        label_count >= MIN_MONTHLY_LABELS
        and agreement_rate >= MIN_AGREEMENT_RATE
        and p0_p1_misses == 0
    ):
        return (
            CalibrationEligibility.BLOCKING_ELIGIBLE,
            JudgeCalibrationStatus.BLOCKING_ENABLED,
        )
    if p0_p1_misses > 0 or agreement_rate < MIN_AGREEMENT_RATE:
        return (
            CalibrationEligibility.BLOCKING_DISABLED,
            JudgeCalibrationStatus.REPORT_ONLY,
        )
    return CalibrationEligibility.REPORT_ONLY, JudgeCalibrationStatus.REPORT_ONLY


def run_monthly_calibration(
    examples: list[CalibrationExample],
    *,
    month: str,
    store: CalibrationStore | None = None,
) -> CalibrationReport:
    agreement = compute_agreement(examples)
    misses = count_p0_p1_misses(examples)
    eligibility, status = decide_eligibility(
        label_count=len(examples),
        agreement_rate=agreement,
        p0_p1_misses=misses,
    )
    strata: dict[str, int] = {}
    for ex in examples:
        strata[ex.stratum] = strata.get(ex.stratum, 0) + 1

    notes = ""
    if eligibility != CalibrationEligibility.BLOCKING_ELIGIBLE:
        notes = (
            "report-only fallback: insufficient labels, agreement below 85%, "
            "or P0/P1 miss detected"
        )

    report = CalibrationReport(
        calibration_id=f"calib-{uuid4()}",
        month=month,
        label_count=len(examples),
        agreement_rate=round(agreement, 4),
        p0_p1_misses=misses,
        eligibility=eligibility,
        status=status,
        strata_counts=strata,
        notes=notes,
    )
    if store is not None:
        store.add_examples(examples)
        store.save(report)
    return report


def compare_human_vs_judge(
    examples: list[CalibrationExample],
) -> dict[str, Any]:
    """Structured human comparison payload for admin / workers."""
    agreement = compute_agreement(examples)
    misses = count_p0_p1_misses(examples)
    return {
        "label_count": len(examples),
        "agreement_rate": round(agreement, 4),
        "p0_p1_misses": misses,
        "matches": sum(1 for e in examples if e.human_passed == e.judge_passed),
        "mismatches": sum(1 for e in examples if e.human_passed != e.judge_passed),
    }


__all__ = [
    "CalibrationEligibility",
    "CalibrationExample",
    "CalibrationReport",
    "CalibrationStore",
    "MIN_AGREEMENT_RATE",
    "MIN_MONTHLY_LABELS",
    "compare_human_vs_judge",
    "compute_agreement",
    "count_p0_p1_misses",
    "decide_eligibility",
    "run_monthly_calibration",
]
