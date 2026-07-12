"""Immutable analysis freshness and before/after comparison helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StaleCheck:
    is_stale: bool
    reasons: list[str]


def detect_stale_analysis(
    *,
    analysis_resume_version: int,
    current_resume_version: int,
    analysis_jd_hash: str | None,
    current_jd_hash: str | None,
    scoring_version: str = "scoring.v1",
    current_scoring_version: str = "scoring.v1",
    job_refreshable: bool = True,
) -> StaleCheck:
    reasons: list[str] = []
    if int(analysis_resume_version) != int(current_resume_version):
        reasons.append("resume_changed")
    if analysis_jd_hash != current_jd_hash:
        reasons.append("jd_changed")
    if not job_refreshable and analysis_jd_hash:
        reasons.append("job_unavailable")
    if scoring_version != current_scoring_version:
        reasons.append("scoring_superseded")
    return StaleCheck(is_stale=bool(reasons), reasons=reasons)


def compare_analyses(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_dimensions = _by_key(before.get("dimensions") or before.get("dimension_items") or [])
    after_dimensions = _by_key(after.get("dimensions") or after.get("dimension_items") or [])
    before_gaps = _by_id(before.get("gaps") or before.get("requirements") or [])
    after_gaps = _by_id(after.get("gaps") or after.get("requirements") or [])

    resolved = sorted(
        gap_id
        for gap_id, gap in before_gaps.items()
        if gap_id in after_gaps
        and _is_blocking(gap)
        and not _is_blocking(after_gaps[gap_id])
    )
    new = sorted(
        gap_id
        for gap_id, gap in after_gaps.items()
        if gap_id not in before_gaps or (not _is_blocking(before_gaps[gap_id]) and _is_blocking(gap))
    )

    return {
        "before_analysis_id": before.get("id"),
        "after_analysis_id": after.get("id"),
        "score_delta": _num(after.get("overall_score")) - _num(before.get("overall_score")),
        "dimension_deltas": {
            key: round(_num(after_dimensions.get(key, {}).get("score")) - _num(before_dimensions.get(key, {}).get("score")), 2)
            for key in sorted(set(before_dimensions) | set(after_dimensions))
        },
        "gap_changes": {
            "resolved": resolved,
            "new": new,
            "unchanged": sorted(set(before_gaps) & set(after_gaps) - set(resolved)),
        },
        "immutable": True,
    }


def _by_key(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("key")): dict(item) for item in items if item.get("key")}


def _by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id") or item.get("requirement_id")): dict(item) for item in items if item.get("id") or item.get("requirement_id")}


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_blocking(gap: dict[str, Any]) -> bool:
    return str(gap.get("coverage")) in {"missing_evidence", "real_gap", "unknown"}


__all__ = ["StaleCheck", "compare_analyses", "detect_stale_analysis"]
