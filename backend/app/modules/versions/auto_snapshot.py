"""Auto-snapshot placeholder task (Phase 1).

The actual ARQ task body returns `{"skipped": True, "reason": "phase 1 placeholder"}`.
Phase 2 will implement real diff-based snapshots.
"""
from __future__ import annotations

from typing import Any


async def auto_snapshot_branch(ctx: dict[str, Any], branch_id: str) -> dict[str, Any]:
    """ARQ task — Phase 1: no-op.

    Real implementation in Phase 2: load current blocks, find the most
    recent full snapshot, diff against it, and write a `diff_patch`
    version row.
    """
    return {"skipped": True, "reason": "phase 1 placeholder", "branch_id": branch_id}


__all__ = ["auto_snapshot_branch"]
