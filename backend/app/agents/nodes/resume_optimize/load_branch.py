"""M16 node — load_branch: fetch branch blocks and resume context.

Loads all blocks for the target branch and stores them in state.
"""
from __future__ import annotations

from app.agents.state.resume_optimize_state import ResumeOptimizeState
from app.agents.tools.query_resume_blocks import query_resume_blocks
from app.observability import traced_node


@traced_node("resume_optimize.load_branch")
async def load_branch_node(state: ResumeOptimizeState) -> dict:
    """Load the current blocks for the target resume branch."""
    branch_id = state.get("branch_id", "")
    user_id = state.get("user_id", "")

    blocks = await query_resume_blocks(branch_id, user_id=user_id)

    return {
        "current_blocks": blocks,
        "messages": [{"role": "system", "content": f"Loaded {len(blocks)} blocks for branch {branch_id}"}],
    }


__all__ = ["load_branch_node"]