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
from app.agents.checkpointer import get_graph_config
from app.agents.nodes.resume_optimize.apply_or_discard import apply_or_discard_node
from app.agents.nodes.resume_optimize.diff_jd import diff_jd_node
from app.agents.nodes.resume_optimize.load_branch import load_branch_node
from app.agents.nodes.resume_optimize.snapshot import snapshot_node
from app.agents.nodes.resume_optimize.suggest_blocks import suggest_blocks_node
from app.agents.state.resume_optimize_state import ResumeOptimizeState


class ResumeOptimizeGraph(BaseAgent):
    """LangGraph agent for AI-driven resume optimization.

    Flow: load_branch → diff_jd → suggest_blocks → apply_or_discard (interrupt) → snapshot → END
    """

    def __init__(self) -> None:
        self._checkpointer = None

    async def _get_checkpointer(self):
        if self._checkpointer is None:
            from app.agents.checkpointer import get_checkpointer

            self._checkpointer = await get_checkpointer()
        return self._checkpointer

    async def build_graph(self) -> StateGraph:
        """Build the compiled Resume Optimize StateGraph with PostgreSQL checkpointer."""
        builder = StateGraph(ResumeOptimizeState)

        builder.add_node("load_branch", load_branch_node)
        builder.add_node("diff_jd", diff_jd_node)
        builder.add_node("suggest_blocks", suggest_blocks_node)
        builder.add_node("apply_or_discard", apply_or_discard_node)
        builder.add_node("snapshot", snapshot_node)

        builder.set_entry_point("load_branch")
        builder.add_edge("load_branch", "diff_jd")
        builder.add_edge("diff_jd", "suggest_blocks")
        builder.add_edge("suggest_blocks", "apply_or_discard")
        builder.add_conditional_edges(
            "apply_or_discard",
            self._route_after_decision,
            {
                "snapshot": "snapshot",
                END: END,
            },
        )
        builder.add_edge("snapshot", END)

        checkpointer = await self._get_checkpointer()
        return builder.compile(checkpointer=checkpointer, interrupt_after=["apply_or_discard"])

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
    ) -> dict[str, Any]:
        """Resolve interrupt with user decision (apply/discard)."""
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        await graph.aupdate_state(
            config,
            {"decision": decision, "thread_aborted": decision == "discard"},
        )
        result = await graph.ainvoke(None, config)
        return result

    async def get_state(
        self,
        thread_id: str,
    ) -> dict[str, Any]:
        """Get current graph state."""
        from app.agents.checkpointer import get_graph_config

        graph = await self.build_graph()
        config = await get_graph_config(thread_id)
        state = await graph.aget_state(config)

        values = state.values if state.values else {}
        return {
            "thread_id": thread_id,
            "status": "completed" if not state.next else "waiting_interrupt" if "apply_or_discard" in (state.next or []) else "running",
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
