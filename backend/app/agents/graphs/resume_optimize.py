"""M16 Resume Optimize StateGraph — LangGraph agent for AI resume optimization.

Graph structure:
    load_branch → diff_jd → suggest_blocks → apply_or_discard (interrupt!) → snapshot → END

Compiled with interrupt_after=["apply_or_discard"] for human-in-the-loop.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.nodes.resume_optimize.apply_or_discard import apply_or_discard_node
from app.agents.nodes.resume_optimize.diff_jd import diff_jd_node
from app.agents.nodes.resume_optimize.load_branch import load_branch_node
from app.agents.nodes.resume_optimize.snapshot import snapshot_node
from app.agents.nodes.resume_optimize.suggest_blocks import suggest_blocks_node
from app.agents.state.resume_optimize_state import ResumeOptimizeState
from app.observability import traced_node


# US2 AC-3.4 / AC-E2E-5: re-decorated shims with `__name__` matching the
# {role}_{action} suffix.
@traced_node("resume_optimize.load_branch")
async def load_branch(state: Any) -> Any:
    return await load_branch_node(state)


@traced_node("resume_optimize.diff_jd")
async def diff_jd(state: Any) -> Any:
    return await diff_jd_node(state)


@traced_node("resume_optimize.suggest_blocks")
async def suggest_blocks(state: Any) -> Any:
    return await suggest_blocks_node(state)


@traced_node("resume_optimize.apply_or_discard")
async def apply_or_discard(state: Any) -> Any:
    return await apply_or_discard_node(state)


@traced_node("resume_optimize.snapshot")
async def snapshot(state: Any) -> Any:
    return await snapshot_node(state)


class ResumeOptimizeGraph(BaseAgent):
    """LangGraph agent for AI-driven resume optimization.

    Flow: load_branch → diff_jd → suggest_blocks → apply_or_discard (interrupt) → snapshot → END
    """

    async def build_graph(self) -> StateGraph:
        """Build the compiled Resume Optimize StateGraph with PostgreSQL checkpointer."""
        builder = StateGraph(ResumeOptimizeState)

        # US2 FR-003 / AC-3.4: node names follow `{agent}.{role}_{action}`.
        builder.add_node("resume_optimize.load_branch", load_branch)
        builder.add_node("resume_optimize.diff_jd", diff_jd)
        builder.add_node("resume_optimize.suggest_blocks", suggest_blocks)
        builder.add_node("resume_optimize.apply_or_discard", apply_or_discard)
        builder.add_node("resume_optimize.snapshot", snapshot)

        builder.set_entry_point("resume_optimize.load_branch")
        builder.add_edge("resume_optimize.load_branch", "resume_optimize.diff_jd")
        builder.add_edge("resume_optimize.diff_jd", "resume_optimize.suggest_blocks")
        builder.add_edge("resume_optimize.suggest_blocks", "resume_optimize.apply_or_discard")
        builder.add_conditional_edges(
            "resume_optimize.apply_or_discard",
            self._route_after_decision,
            {
                "snapshot": "resume_optimize.snapshot",
                END: END,
            },
        )
        builder.add_edge("resume_optimize.snapshot", END)

        checkpointer = await get_checkpointer()
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_after=["resume_optimize.apply_or_discard"],
        )

    def _route_after_decision(self, state: ResumeOptimizeState) -> Literal["snapshot", "__end__"]:
        """Route to snapshot if apply, otherwise end."""
        decision = state.get("decision")
        thread_aborted = state.get("thread_aborted", False)

        if decision == "apply" and not thread_aborted:
            return "snapshot"
        return END

    async def start(
        self,
        user_id: str,
        branch_id: str,
        target_jd: str,
    ) -> str:
        """Initialize the graph (runs load_branch → diff_jd → suggest_blocks → interrupt)."""
        thread_id = str(uuid4())
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        await graph.ainvoke(
            {
                "user_id": user_id,
                "branch_id": branch_id,
                "target_jd": target_jd,
                "thread_id": thread_id,
            },
            config,
        )
        return thread_id

    async def confirm(
        self,
        thread_id: str,
        decision: str,
        accepted_patch_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        """Resolve interrupt with user decision (apply/discard).

        accepted_patch_indices: when decision='apply', pass list of patch indices
        to accept (US5 per-patch). None = apply all patches.
        """
        config = await get_graph_config(thread_id)

        update: dict[str, Any] = {
            "decision": decision,
            "thread_aborted": decision == "discard",
        }
        if decision == "apply" and accepted_patch_indices is not None:
            update["accepted_patch_indices"] = accepted_patch_indices

        await retry_graph_op(self.build_graph, config, "aupdate_state", update)
        result = await retry_graph_op(self.build_graph, config, "ainvoke", None, state_first=True)
        return result

    async def get_state(
        self,
        thread_id: str,
    ) -> dict[str, Any]:
        """Get current graph state."""
        config = await get_graph_config(thread_id)
        state = await retry_graph_op(self.build_graph, config, "aget_state")

        values = state.values if state.values else {}
        return {
            "thread_id": thread_id,
            "status": "completed" if not state.next else "waiting_interrupt" if "resume_optimize.apply_or_discard" in (state.next or []) else "running",
            "current_node": state.next[0] if state.next else None,
            "summary": values.get("summary"),
            "proposed_patches": values.get("proposed_patches"),
        }


# Singleton
_resume_optimize_graph: ResumeOptimizeGraph | None = None


def get_resume_optimize_graph() -> ResumeOptimizeGraph:
    global _resume_optimize_graph
    if _resume_optimize_graph is None:
        _resume_optimize_graph = ResumeOptimizeGraph()
    return _resume_optimize_graph


__all__ = ["ResumeOptimizeGraph", "get_resume_optimize_graph"]
