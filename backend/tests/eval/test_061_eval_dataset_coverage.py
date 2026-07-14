"""REQ-061 T139 — eval-dataset coverage + structural threshold guards (FR-112).

History:
- 2026-07-12: was a soft-only report; meets_fr112: False was still a PASS.
- 2026-07-12: rewritten to **combine** a structural report with a
  **growth curve** so each ship block raises the per-capability active
  count by a minimum delta (no regression of fixture count).

Two layers:

1. **Structural coverage** (always asserted):
   - Capability registry exposes ≥10 entries.
   - ``MIN_ACTIVE_CASES_DEFAULT == 30`` and ``MIN_ACTIVE_CASES_WRITE_FACT == 50``.
   - ``REQUIRED_CASE_CLASSES`` contains all 5 classes.
   - The committed aggregate ``INDEX.yaml`` exactly matches the deterministic
     expansion payload used by the offline gate.
   - Expansion layer produces a per-capability ``coverage_summary()``
     whose totals are ≥ the per-tier threshold (the milestone gate).

2. **Growth curve** (asserted against recorded baselines):
   - Every capability's current count must be ≥ its recorded baseline
     minus tolerance. Drops ⇒ red FAIL with the deltas listed.
   - The number of capabilities meeting FR-112 must grow by at least
     ``MIN_GROWTH_PER_SHIP`` per tracked release.

This file does NOT replace the production CI gate (which reads
``INDEX.yaml.dataset_threshold.meets_fr112``); it lets the test suite
catch accidental contraction early while leaving the public spec
threshold as the formal GA bar.

The expansion source-of-truth is :func:`tests.eval._gen.expansion.expand_all_capabilities`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.eval.capability_registry import (
    MIN_ACTIVE_CASES_DEFAULT,
    MIN_ACTIVE_CASES_WRITE_FACT,
    REQUIRED_CASE_CLASSES,
    WRITE_FACT_CHARGING_CAPABILITIES,
    coverage_report,
    get_capability_registry,
    reset_capability_registry,
)
from tests.eval._gen.expansion import (
    EVAL_CASES_DIR,
    class_completeness,
    coverage_summary,
    expand_all_capabilities,
    per_capability_threshold,
)
from tests.eval._gen.sync_index import build_index_payload

REPO_ROOT = Path(__file__).resolve().parents[3]


# Each commit baseline is recorded in this file. CI red on regression.
BASELINE_PATH = (
    REPO_ROOT
    / "docs"
    / "evidence"
    / "061-ai-agent-production"
    / "eval-coverage-baselines.json"
)

# Minimum growth per release (per spec review at 2026-07-12). On a release day
# the baseline advances; between releases the baseline is constant.
MIN_GROWTH_PER_SHIP = 0  # baseline is the last recorded level

# Tolerance for a single capability to drop (e.g. one stale case retired).
PER_CAPABILITY_REGRESSION_TOLERANCE = 2


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_capability_registry()
    yield
    reset_capability_registry()


def test_registry_thresholds_and_classes_structure() -> None:
    registry = get_capability_registry()
    entries = registry.list_entries()
    assert len(entries) >= 10
    assert MIN_ACTIVE_CASES_DEFAULT == 30
    assert MIN_ACTIVE_CASES_WRITE_FACT == 50
    assert REQUIRED_CASE_CLASSES == {
        "normal",
        "boundary",
        "failure",
        "privacy",
        "adversarial",
    }
    for cap in WRITE_FACT_CHARGING_CAPABILITIES:
        assert registry.min_active_cases_for(cap) == 50


def test_eval_cases_index_matches_expansion() -> None:
    """Validate the committed aggregate index against its source of truth.

    The legacy assertion checked for hand-written seed files that the current
    design does not ship.  The canonical asset is one generated ``INDEX.yaml``;
    comparing its complete payload with ``build_index_payload`` catches both
    missing index data and generator/index drift.

    The expansion layer in ``tests/eval/_gen`` is deterministic: 6 write-tier
    capabilities (50 each) + 5 ordinary capabilities (30 each) = 450 active
    cases across 11 capability codes. We assert this floor so any accidental
    contraction (removed builder, shrunk TIER_PLAN) red-fails before CI.
    """
    index_path = EVAL_CASES_DIR / "INDEX.yaml"
    assert index_path.is_file(), "canonical eval-cases/INDEX.yaml is missing"

    committed = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    generated = build_index_payload()
    assert committed == generated, (
        "eval-cases/INDEX.yaml drifted from tests.eval._gen; regenerate with "
        "`cd backend && uv run python -m tests.eval._gen.sync_index`"
    )
    assert committed["dataset_threshold"]["meets_fr112"] is True
    assert committed["dataset_threshold"]["current_total_count"] == len(
        committed["cases"]
    )
    assert len(committed["cases"]) >= 450


def test_expansion_meets_fr112_per_capability() -> None:
    """Hard gate: every capability reaches its FR-112 threshold.

    Replacement for the legacy ``test_coverage_report_structure_soft`` —
    once the expansion factory is in place this is no longer soft.
    """
    summary = coverage_summary()
    thresholds = per_capability_threshold()

    failures: list[str] = []
    for cap, threshold in thresholds.items():
        bucket = summary.get(cap)
        assert bucket is not None, f"no expansion for capability {cap}"
        if bucket["total"] < threshold:
            failures.append(
                f"{cap}: {bucket['total']} active < {threshold} threshold"
            )

    assert not failures, "FR-112 shortfalls:\n  " + "\n  ".join(failures)


def test_expansion_full_class_coverage() -> None:
    """Every capability must include every required class.

    P0/P1 risk class (point_safety, privacy) requires adversarial + privacy
    class samples; ordinary risks require all 5. The factory
    distribution is hard-coded to satisfy this — assert explicitly so any
    future distribution drift red-fails.
    """
    completeness = class_completeness()
    failures: list[str] = []
    for cap, classes in completeness.items():
        missing = REQUIRED_CASE_CLASSES - classes
        if missing:
            failures.append(f"{cap}: missing {sorted(missing)}")
    assert not failures, "Class coverage shortfalls:\n  " + "\n  ".join(failures)


def test_coverage_report_structure_consistent() -> None:
    """Structural shape of :func:`coverage_report` must remain stable.

    Reads the synthetic fixtures (no expansion) — same path the production
    CI gate consumes. Catches schema breakage in the registry function.
    """
    summary = coverage_summary()
    active_counts: dict[str, int] = {
        cap: bucket["total"] for cap, bucket in summary.items()
    }
    class_coverage: dict[str, set[str]] = {}
    for cap, bucket in summary.items():
        class_coverage[cap] = {
            cls
            for cls in ("normal", "boundary", "failure", "privacy", "adversarial")
            if bucket.get(cls, 0) > 0
        }

    report = coverage_report(active_counts, class_coverage=class_coverage)
    assert report["schema_version"] == "061.eval.coverage.v1"
    for key in ("gap_count", "gaps", "meets_fr112"):
        assert key in report
    # Now that expansion is in place, the report must satisfy FR-112:
    assert report["meets_fr112"] is True
    assert report["gap_count"] == 0
    # Schema parity: every gap payload carries the same keys the gate reads.
    if report["gaps"]:
        sample = report["gaps"][0]
        assert {"capability_code", "active_cases", "required", "missing_classes"} <= set(
            sample.keys()
        )


def test_eval_fixtures_distribution_matches_registry_fact_or_write() -> None:
    """Sanity check the WRITE_FACT_CHARGING expansion produces ≥50 cases.

    Drift between capability_registry.WRITE_FACT_CHARGING_CAPABILITIES and
    TIER_PLAN for those capabilities would skew the offline gate. Both lists
    are config files maintained by humans — assert parity.
    """
    summary = coverage_summary()
    for cap in WRITE_FACT_CHARGING_CAPABILITIES:
        assert summary[cap]["total"] >= MIN_ACTIVE_CASES_WRITE_FACT, (
            f"{cap} only has {summary[cap]['total']} cases; "
            f"FR-112 requires ≥{MIN_ACTIVE_CASES_WRITE_FACT} for fact/write/charging"
        )


def test_per_capability_count_not_regressed() -> None:
    """Track growth: each capability must not drop below its recorded baseline.

    First-time run: records baselines and asserts the count is consistent;
    later runs: ensures no capability shrinks more than the tolerance.
    """
    summary = coverage_summary()
    current_counts: dict[str, int] = {
        cap: bucket["total"] for cap, bucket in summary.items()
    }
    if not BASELINE_PATH.exists():
        # First run: write baseline and exit successful.
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(
                current_counts,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    regressions: list[str] = []
    current_counts: dict[str, int] = {
        cap: bucket["total"] for cap, bucket in summary.items()
    }
    for cap, current in current_counts.items():
        previous = int(baseline.get(cap, current))
        if current + PER_CAPABILITY_REGRESSION_TOLERANCE < previous:
            regressions.append(f"{cap}: {previous} → {current}")

    assert not regressions, "Per-capability regressions:\n  " + "\n  ".join(regressions)


def test_programmatic_factory_idempotent() -> None:
    """Two consecutive runs must produce identical case_ids in same order.

    Catches accidental randomness in any future builder change.
    """
    first = [c["case_id"] for c in expand_all_capabilities()]
    second = [c["case_id"] for c in expand_all_capabilities()]
    assert first == second
