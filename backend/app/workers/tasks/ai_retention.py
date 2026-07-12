"""REQ-061 T172 — AI retention / deletion orchestrator re-run surface.

Re-runs the lifecycle deletion plan against §10 matrix rows. Full
restore-and-redelete evidence is recorded under docs/evidence when live.
"""

from __future__ import annotations

from typing import Any

from app.modules.ai_runtime.privacy.service import LIFECYCLE_REGISTRY, plan_provenance_deletion

SECTION_10_MATRIX_STORES: tuple[str, ...] = (
    "ai_task",
    "ai_task_event",
    "point_ledger_event",
    "authorization_receipt",
    "checkpoint",
    "outbox",
)


def retention_matrix_coverage() -> dict[str, Any]:
    codes = {row["store"] for row in LIFECYCLE_REGISTRY}
    missing = [s for s in SECTION_10_MATRIX_STORES if s not in codes]
    return {
        "required": list(SECTION_10_MATRIX_STORES),
        "registered": sorted(codes),
        "missing": missing,
        "complete": not missing,
    }


def plan_full_deletion(*, root_task_id: str, subject_user_id: str) -> dict[str, Any]:
    plan = plan_provenance_deletion(
        root_task_id=root_task_id, subject_user_id=subject_user_id
    )
    coverage = retention_matrix_coverage()
    return {
        "plan": plan,
        "matrix": coverage,
        "evidence_required": True,
        "restore_and_redelete": "pending_live_evidence",
    }


__all__ = [
    "SECTION_10_MATRIX_STORES",
    "plan_full_deletion",
    "retention_matrix_coverage",
]
