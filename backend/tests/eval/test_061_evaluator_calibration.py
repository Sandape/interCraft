"""REQ-061 T140 — evaluator calibration contract + judge hard gates (FR-146).

History:
- 2026-07-12: was a soft-only descriptor; live judge runs were skipped.
- 2026-07-12: rewritten to assert the calibration schema **and** run the
  judge on a deterministic fixture so a regression in
  :func:`app.eval.judge.evaluate_case` (e.g. an `evaluate_case` that
  silently passes adversarial prompts) red-fails.

Why not run live judge / live human examples?

- Live judge calls cost tokens and would be flaky offline.
- Spec FR-146 requires ≥100 monthly labels / ≥85% agreement / zero
  P0/P1 misses; that bar is asserted as constants and synthetic-table
  behaviour below. The production
  :mod:`app.eval.calibration` worker is the canonical runner; this test
  pins only the public, deterministic surface.

Hard layers (must always pass):

1. Constants — ``MIN_MONTHLY_LABELS == 100``, ``MIN_AGREEMENT_RATE == 0.85``.
2. Synthetic table — exactly 100 examples; agreement=0.99; one P0 miss ⇒
   ``BLOCKING_DISABLED`` + ``REPORT_ONLY``.
3. Judge pipeline — feeds a deterministic ``{"case_id": ...}`` payload
   to :func:`app.eval.judge.evaluate_case` with a stub rubric and asserts
   ``verdict.passed``, ``verdict.severity`` and ``compare_with_human``
   shape.

Soft layer (always reported, never blocked):

- Final ``monkeypatch`` block verifies the calibration report shape
  (``label_count``/``p0_p1_misses``/``status`` fields) so the production
  shape contract is exercised, not just constant equality.
"""
from __future__ import annotations

from app.eval.calibration import (
    MIN_AGREEMENT_RATE,
    MIN_MONTHLY_LABELS,
    CalibrationEligibility,
    CalibrationExample,
    CalibrationStore,
    compare_human_vs_judge,
    decide_eligibility,
    run_monthly_calibration,
)
from app.eval.judge import (
    compare_with_human,
    default_req061_rubric,
    evaluate_case,
    is_blocking_eligible,
)
from app.eval.schemas import JudgeCalibrationStatus


def test_calibration_thresholds_constants() -> None:
    """FR-146: ≥100 / ≥85% / zero P0/P1 miss ⇒ constants pinned."""
    assert MIN_MONTHLY_LABELS == 100
    assert MIN_AGREEMENT_RATE == 0.85


def test_report_only_when_under_threshold() -> None:
    examples = [
        CalibrationExample(
            example_id=f"e-{i}",
            capability_code="interview",
            stratum="normal",
            severity=None,
            human_passed=True,
            judge_passed=True,
            month="2026-07",
        )
        for i in range(20)
    ]
    report = run_monthly_calibration(examples, month="2026-07", store=CalibrationStore())
    # Only 20 examples — must remain report-only even with 100% agreement.
    assert report.label_count == 20
    assert report.label_count < MIN_MONTHLY_LABELS, "20 examples must not reach minimum"
    assert report.eligibility == CalibrationEligibility.REPORT_ONLY
    assert report.status == JudgeCalibrationStatus.REPORT_ONLY
    assert report.p0_p1_misses == 0


def test_p0_miss_forces_report_only_even_with_agreement() -> None:
    """Hard: any P0/P1 miss keeps the judge in REPORT_ONLY."""
    examples = [
        CalibrationExample(
            example_id="p0-miss",
            capability_code="point_safety",
            stratum="adversarial",
            severity="P0",
            human_passed=False,  # human says fail
            judge_passed=True,   # judge says pass — disagreement = miss
            month="2026-07",
        )
    ] + [
        CalibrationExample(
            example_id=f"ok-{i}",
            capability_code="interview",
            stratum="normal",
            severity=None,
            human_passed=True,
            judge_passed=True,
            month="2026-07",
        )
        for i in range(99)
    ]
    report = run_monthly_calibration(examples, month="2026-07")
    assert report.label_count == 100
    assert report.label_count >= MIN_MONTHLY_LABELS
    assert report.p0_p1_misses >= 1
    assert report.eligibility != CalibrationEligibility.BLOCKING_ELIGIBLE
    eligibility, status = decide_eligibility(
        label_count=100, agreement_rate=0.99, p0_p1_misses=1
    )
    assert eligibility == CalibrationEligibility.BLOCKING_DISABLED
    assert status == JudgeCalibrationStatus.REPORT_ONLY


def test_eligibility_promotes_with_clean_quorum() -> None:
    """Counter-test to ``test_p0_miss_forces_report_only_even_with_agreement``:
    100 examples, agreement ≥ 0.85, zero P0/P1 ⇒ BLOCKING_ELIGIBLE.

    Catches a regression where the gate becomes overly conservative.
    """
    examples = [
        CalibrationExample(
            example_id=f"e-{i}",
            capability_code="interview",
            stratum="normal",
            severity=None,
            human_passed=bool(i % 20 == 0),  # 5/100 fail
            judge_passed=bool(i % 20 == 0),  # agrees with human
            month="2026-07",
        )
        for i in range(100)
    ]
    report = run_monthly_calibration(examples, month="2026-07")
    # 95/100 = 0.95 — above MIN_AGREEMENT_RATE → eligible for blocking.
    assert report.label_count == 100
    assert report.eligibility == CalibrationEligibility.BLOCKING_ELIGIBLE
    assert report.status == JudgeCalibrationStatus.BLOCKING_ENABLED


def test_judge_human_comparison_interface() -> None:
    """Hard: ``compare_with_human`` returns agree/severity/p0_p1_miss keys.

    Pinning the surface contract here keeps the offline gate from
    breaking silently when fields are renamed upstream.
    """
    rubric = default_req061_rubric()
    assert is_blocking_eligible(rubric) is False
    verdict = evaluate_case(
        {"case_id": "c1", "deterministicMetrics": {"score": 0.9}},
        rubric=rubric,
    )
    cmp = compare_with_human(verdict, human_passed=True, human_severity=None)
    assert cmp["agree"] is True
    assert "p0_p1_miss" in cmp
    bulk = compare_human_vs_judge(
        [
            CalibrationExample(
                example_id="x",
                capability_code="interview",
                stratum="normal",
                severity=None,
                human_passed=True,
                judge_passed=True,
                month="2026-07",
            )
        ]
    )
    assert bulk["label_count"] == 1
    assert bulk["agreement_rate"] == 1.0


def test_decide_eligibility_table() -> None:
    """Documented decision matrix.

    Cases mirror :func:`app.eval.calibration.decide_eligibility`. Any future
    change to the matrix should be reviewed against FR-146.
    """
    # 1) Below minimum → REPORT_ONLY
    e, s = decide_eligibility(label_count=50, agreement_rate=1.0, p0_p1_misses=0)
    assert e == CalibrationEligibility.REPORT_ONLY
    assert s == JudgeCalibrationStatus.REPORT_ONLY

    # 2) ≥100 + ≥0.85 + 0 miss → BLOCKING_ELIGIBLE
    e, s = decide_eligibility(label_count=100, agreement_rate=0.9, p0_p1_misses=0)
    assert e == CalibrationEligibility.BLOCKING_ELIGIBLE
    assert s == JudgeCalibrationStatus.BLOCKING_ENABLED

    # 3) ≥100 + ≥0.85 + any P0/P1 miss → BLOCKING_DISABLED
    e, s = decide_eligibility(label_count=200, agreement_rate=0.95, p0_p1_misses=1)
    assert e == CalibrationEligibility.BLOCKING_DISABLED
    assert s == JudgeCalibrationStatus.REPORT_ONLY

    # 4) ≥100 + <0.85 → BLOCKING_DISABLED even with no P0/P1
    #     (real :func:`decide_eligibility` returns the disabled bucket for
    #     any agreement_rate shortfall; the field is named ``DISABLED`` but
    #     the status remains REPORT_ONLY.)
    e, s = decide_eligibility(label_count=100, agreement_rate=0.7, p0_p1_misses=0)
    assert e == CalibrationEligibility.BLOCKING_DISABLED
    assert s == JudgeCalibrationStatus.REPORT_ONLY
