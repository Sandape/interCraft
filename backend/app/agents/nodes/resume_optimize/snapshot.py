"""M16 node — snapshot: persist changes and create version record.

Called after apply_or_discard when decision is 'apply'.
Applies JSON Patch to blocks, creates a version snapshot.

US5: When `accepted_patch_indices` is set in state, only those patches
are applied (per-patch accept/reject). None = apply all.
"""
from __future__ import annotations

from app.agents.state.resume_optimize_state import ResumeOptimizeState
from app.observability import traced_node
from app.services.resume_optimize_service import ResumeOptimizeService


def _filter_patches(
    patches: list[dict],
    accepted_indices: list[int] | None,
) -> list[dict]:
    """Return only the patches the user accepted. None = all."""
    if accepted_indices is None:
        return patches
    accepted_set = set(accepted_indices)
    return [p for i, p in enumerate(patches) if i in accepted_set]


@traced_node("resume_optimize.snapshot")
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
    accepted_indices = state.get("accepted_patch_indices")
    summary = state.get("summary", "AI optimization")

    selected = _filter_patches(proposed_patches, accepted_indices)

    service = ResumeOptimizeService()
    try:
        version_id = await service.apply_patches_and_version(
            branch_id=branch_id,
            user_id=user_id,
            patches=selected,
            summary=summary,
        )
        skipped = len(proposed_patches) - len(selected)
        msg = f"Applied {len(selected)} patches. Version {version_id} created."
        if skipped > 0:
            msg += f" Skipped {skipped} rejected patches."
        return {
            "messages": [{"role": "system", "content": msg}],
        }
    except Exception as exc:
        return {
            "messages": [{"role": "system", "content": f"Failed to apply patches: {exc}"}],
        }


__all__ = ["snapshot_node"]