"""Sync ``specs/061-ai-agent-production/eval-cases/INDEX.yaml`` with generator.

REQ-061 US11 T144 left ``INDEX.yaml`` as the machine-readable registry that
``bootstrap.yaml safety.eval_dataset_threshold_required`` enforces against.

This module regenerates that file from the **expansion layer** so any drift
in seeds, factories or TIER_PLAN shows up in the same commit as the
``tests/eval/_gen`` source-of-truth.

The script is intentionally tiny — it does NOT ship seeds to disk and it
does NOT auto-generate new seeds; it only re-emits the aggregated INDEX
used by the offline gate.

Usage::

    cd backend && uv run --no-sync python -m tests.eval._gen.sync_index
"""
from __future__ import annotations

from pathlib import Path

import yaml

from tests.eval._gen.expansion import (
    EVAL_CASES_DIR,
    coverage_summary,
    per_capability_threshold,
)
from tests.eval._gen.registry import TIER_PLAN


def _summary_block() -> dict[str, object]:
    summary = coverage_summary()
    per_cap = {
        cap: {
            "total": bucket["total"],
            "normal": bucket["normal"],
            "boundary": bucket["boundary"],
            "failure": bucket["failure"],
            "privacy": bucket["privacy"],
            "adversarial": bucket["adversarial"],
            "threshold": per_capability_threshold()[cap],
            "meets": bucket["total"] >= per_capability_threshold()[cap],
        }
        for cap, bucket in sorted(summary.items())
    }
    by_class = {
        cls: sum(bucket[cls] for bucket in summary.values())
        for cls in ("normal", "boundary", "failure", "privacy", "adversarial")
    }
    meets = sum(1 for v in per_cap.values() if v["meets"])
    return {
        "per_capability_count": per_cap,
        "count_summary": {
            "total_fixtures": sum(b["total"] for b in summary.values()),
            "capabilities": len(summary),
            "by_class": by_class,
            "min_per_capability": min(b["total"] for b in summary.values()),
            "max_per_capability": max(b["total"] for b in summary.values()),
            "capabilities_meeting_threshold": meets,
            "capabilities_below_threshold": len(summary) - meets,
        },
    }


def _cases_block() -> list[dict[str, str]]:
    """Emit one record per case, sorted by capability + class + idx."""
    rows: list[dict[str, str]] = []
    from tests.eval._gen.expansion import expand_all_capabilities

    for case in expand_all_capabilities():
        if case.get("status") != "active":
            continue
        # Read the rel path from the seed file_path when present; otherwise
        # the synthetic case is not a file on disk.
        file_path = case.get("file_path") or ""
        rel = ""
        if file_path:
            try:
                rel = str(Path(file_path).resolve().relative_to(EVAL_CASES_DIR.resolve()))
            except ValueError:
                rel = ""
        rows.append({
            "case_id": str(case["case_id"]),
            "file": rel or f"<programmatic:{case['capability_code']}/{case['case_class']}>",
            "capability_code": str(case["capability_code"]),
            "action_code": str(case["action_code"]),
            "case_class": str(case["case_class"]),
            "source": str(case.get("source", "programmatic")),
        })
    rows.sort(key=lambda r: (r["capability_code"], r["case_class"], r["case_id"]))
    return rows


def build_index_payload() -> dict[str, object]:
    return {
        "feature_id": "061-ai-agent-production",
        "spec_hash": "auto-generated-by-tests-eval-gen",
        "generated_at": "live",
        "dataset_threshold": {
            "ordinary_minimum": 30,
            "fact_or_write_minimum": 50,
            "current_total_count": sum(b["total"] for b in coverage_summary().values()),
            "meets_fr112": all(
                b["total"] >= per_capability_threshold()[cap]
                for cap, b in coverage_summary().items()
            ),
            "source": "tests.eval._gen.expansion.expand_all_capabilities",
        },
        "tier_plan": {
            cap: {"target_count": plan.target_count, "distribution": dict(plan.distribution)}
            for cap, plan in sorted(TIER_PLAN.items())
        },
        "cases": _cases_block(),
        **_summary_block(),
    }


def write_index(path: Path | None = None) -> Path:
    target = path or (EVAL_CASES_DIR / "INDEX.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_index_payload()
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120)
    target.write_text(text, encoding="utf-8")
    return target


if __name__ == "__main__":
    written = write_index()
    print(f"wrote {written}")
