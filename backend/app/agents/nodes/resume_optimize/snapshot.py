"""M16 node — snapshot: persist changes and create version record.

Called after apply_or_discard when decision is 'apply'.
Applies JSON Patch to blocks, creates a version snapshot.
"""
from __future__ import annotations

from app.agents.state.resume_optimize_state import ResumeOptimizeState
from app.services.resume_optimize_service import ResumeOptimizeService


async def snapshot_node(state: ResumeOptimizeState) -> dict:
    """Apply patches and create a version snapshot."""
    decision = state.get("decision")
    if decision != "apply":
        return {
            "messages": [{"role": "system", "content": "Skipped — decision was not 'apply'."}],
        }

    branch_id = state.get("branch_id", "")
    user_id = state.get("user_id", "")
    proposed_patches = state.get("proposed_patches", [])
    summary = state.get("summary", "AI optimization")

    service = ResumeOptimizeService()
    try:
        version_id = await service.apply_patches_and_version(
            branch_id=branch_id,
            user_id=user_id,
            patches=proposed_patches,
            summary=summary,
        )
        return {
            "messages": [{"role": "system", "content": f"Applied {len(proposed_patches)} patches. Version {version_id} created."}],
        }
    except Exception as exc:
        return {
            "messages": [{"role": "system", "content": f"Failed to apply patches: {exc}"}],
        }


__all__ = ["snapshot_node"]
