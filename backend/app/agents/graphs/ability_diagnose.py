"""M18 Ability Diagnose StateGraph — LangGraph agent for post-interview ability diagnosis.

Graph structure:
    aggregate_scores → compare_baseline → generate_insight → update_dimensions → END

Triggered by ARQ task diagnose_after_interview.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_graph_config
from app.agents.nodes.ability_diagnose.aggregate_scores import aggregate_scores_node
from app.agents.nodes.ability_diagnose.compare_baseline import compare_baseline_node
from app.agents.nodes.ability_diagnose.generate_insight import generate_insight_node
from app.agents.nodes.ability_diagnose.update_dimensions import update_dimensions_node
from app.agents.state.ability_diagnose_state import AbilityDiagnoseState


class AbilityDiagnoseGraph(BaseAgent):
    """LangGraph agent for post-interview ability diagnosis.

    Flow: aggregate_scores → compare_baseline → generate_insight → update_dimensions → END
    """

    def __init__(self) -> None:
        self._checkpointer = None

    async def _get_checkpointer(self):
        if self._checkpointer is None:
            from app.agents.checkpointer import get_checkpointer

            self._checkpointer = await get_checkpointer()
        return self._checkpointer

    async def build_graph(self) -> StateGraph:
        builder = StateGraph(AbilityDiagnoseState)

        builder.add_node("aggregate_scores", aggregate_scores_node)
        builder.add_node("compare_baseline", compare_baseline_node)
        builder.add_node("generate_insight", generate_insight_node)
        builder.add_node("update_dimensions", update_dimensions_node)

        builder.set_entry_point("aggregate_scores")
        builder.add_edge("aggregate_scores", "compare_baseline")
        builder.add_edge("compare_baseline", "generate_insight")
        builder.add_edge("generate_insight", "update_dimensions")
        builder.add_edge("update_dimensions", END)

        checkpointer = await self._get_checkpointer()
        return builder.compile(checkpointer=checkpointer)

    async def run(self, user_id: str, session_id: str) -> dict:
        """Execute the full ability diagnosis pipeline."""
        thread_id = f"diag-{session_id}"
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        result = await graph.ainvoke(
            {
                "user_id": user_id,
                "session_id": session_id,
                "thread_id": thread_id,
            },
            config,
        )
        return result


_ability_diagnose_graph: AbilityDiagnoseGraph | None = None


def get_ability_diagnose_graph() -> AbilityDiagnoseGraph:
    global _ability_diagnose_graph
    if _ability_diagnose_graph is None:
        _ability_diagnose_graph = AbilityDiagnoseGraph()
    return _ability_diagnose_graph


__all__ = ["AbilityDiagnoseGraph", "get_ability_diagnose_graph"]
