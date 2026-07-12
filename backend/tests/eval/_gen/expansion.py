"""Expansion entry point — produce every active case in one list.

Combines:

- 13 hand-written seeds in ``specs/061-ai-agent-production/eval-cases/**``
  (anchor: real prompt/response traces, ``source="manual"``).
- Programmatic variants produced by :mod:`tests.eval._gen.factories`
  according to :mod:`tests.eval._gen.registry` ``TIER_PLAN``
  (``source="programmatic"``).

The result is what's loaded for eval inference — both the offline fixture
harness and the coverage test read through this function so seed drift and
synthetic drift stay in lockstep.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from app.eval.capability_registry import (
    REQUIRED_CASE_CLASSES,
    WRITE_FACT_CHARGING_CAPABILITIES,
)
from tests.eval._gen.factories import BUILDERS
from tests.eval._gen.registry import TIER_PLAN


REPO_ROOT = Path(__file__).resolve().parents[3]
# backend/tests/eval/_gen/expansion.py → parents[3] = backend. Project root is one up.
PROJECT_ROOT = REPO_ROOT.parent
EVAL_CASES_DIR = PROJECT_ROOT / "specs" / "061-ai-agent-production" / "eval-cases"


def _load_seed_fixtures() -> list[dict[str, Any]]:
    """Load every ``.json/.yaml/.yml`` seed fixture under ``EVAL_CASES_DIR``.

    Files that are clearly registry artefacts (top-level ``INDEX.yaml``) are
    skipped — only records shaped like cases (containing ``case_id`` and
    ``capability_code``) are kept.
    """
    cases: list[dict[str, Any]] = []
    if not EVAL_CASES_DIR.is_dir():
        return cases
    for path in sorted(EVAL_CASES_DIR.rglob("*")):
        if path.is_dir() or path.name == "INDEX.yaml":
            continue
        if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
        if not isinstance(data, dict):
            continue
        if "case_id" in data and "capability_code" in data:
            cases.append(data)
    return cases


def _programmatic_variants() -> list[dict[str, Any]]:
    """Build the synthetic tail to complement seed fixtures.

    Reads the seed counts per (capability, class) and asks the per-capability
    builder for **additional** cases up to the TIER_PLAN distribution.

    Important: ``TIER_PLAN.target_count`` is the **total per capability**
    (seed + synthetic). We never duplicate a (cap, class, index) — index is
    sized from the seed count for that class so two runs of this function
    yield the same list.
    """
    seed_cases = _load_seed_fixtures()
    by_cap_class: Counter[tuple[str, str]] = Counter()
    for case in seed_cases:
        if case.get("status") != "active":
            continue
        by_cap_class[(str(case["capability_code"]), str(case["case_class"]))] += 1

    variants: list[dict[str, Any]] = []
    for capability, plan in TIER_PLAN.items():
        builder = BUILDERS.get(capability)
        if builder is None:
            continue
        for case_class, target_total in plan.distribution.items():
            seed_count = by_cap_class.get((capability, case_class), 0)
            needed = max(target_total - seed_count, 0)
            for offset in range(needed):
                # Use offset past the seed count to avoid collision.
                case = builder(seed_count + offset, case_class)
                variants.append(case)
    return variants


def expand_all_capabilities() -> list[dict[str, Any]]:
    """Public aggregator — seeds + synthetic variants, all ``status=='active'``."""
    return _load_seed_fixtures() + _programmatic_variants()


def coverage_summary() -> dict[str, Any]:
    """Return ``{capability_code: {class: count, total: N}}`` for assertions."""
    cases = expand_all_capabilities()
    summary: dict[str, dict[str, Any]] = {}
    for case in cases:
        if case.get("status") != "active":
            continue
        cap = str(case["capability_code"])
        cls = str(case["case_class"])
        bucket = summary.setdefault(
            cap, {"total": 0, "normal": 0, "boundary": 0, "failure": 0, "privacy": 0, "adversarial": 0}
        )
        bucket["total"] += 1
        bucket[cls] = bucket.get(cls, 0) + 1
    return summary


def per_capability_threshold() -> dict[str, int]:
    """Mirror of ``capability_registry.min_active_cases_for`` for tests."""
    return {
        cap: (50 if cap in WRITE_FACT_CHARGING_CAPABILITIES else 30)
        for cap in TIER_PLAN
    }


def class_completeness() -> dict[str, set[str]]:
    """Return ``{capability_code: {class, ...}}`` for missing-class checks."""
    cases = expand_all_capabilities()
    out: dict[str, set[str]] = {}
    for case in cases:
        if case.get("status") != "active":
            continue
        cap = str(case["capability_code"])
        cls = str(case["case_class"])
        out.setdefault(cap, set()).add(cls)
    return out


# Compatibility export — keep test_061_eval_dataset_coverage using one symbol.
REQUIRED_CLASSES = REQUIRED_CASE_CLASSES


__all__ = [
    "EVAL_CASES_DIR",
    "PROJECT_ROOT",
    "REPO_ROOT",
    "REQUIRED_CLASSES",
    "class_completeness",
    "coverage_summary",
    "expand_all_capabilities",
    "per_capability_threshold",
]
