"""InterviewGraph — LangGraph StateGraph for interview flow (T029, T018).

Supervisor graph structure:
    intake → interview_planner (planner subgraph) → planner_complete
    → interviewer → score → (condition: current_question < 5 → interviewer, else → report)

Uses PostgreSQL checkpointer for state persistence.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.interview.nodes.intake import intake_node
from app.agents.interview.nodes.question_gen import question_gen_node
from app.agents.interview.nodes.report import report_node
from app.agents.interview.nodes.score import score_node
from app.agents.interview.planner_graph import get_planner_subgraph
from app.agents.interview.state import InterviewGraphState


class InterviewGraph(BaseAgent):
    """LangGraph agent for AI-powered mock interviews.

    Supervisor flow: intake → interview_planner → planner_complete
                     → interviewer <-> score (x5) → report
    """

    MAX_QUESTIONS = 5

    async def build_graph(self) -> StateGraph:
        """Build the compiled interview StateGraph with PostgreSQL checkpointer."""
        builder = StateGraph(InterviewGraphState)

        planner_subgraph = get_planner_subgraph()

        # Add nodes
        builder.add_node("intake", intake_node)
        builder.add_node("interview_planner", planner_subgraph)
        builder.add_node("planner_complete", _planner_complete_node)
        builder.add_node("interviewer", question_gen_node)
        builder.add_node("score", score_node)
        builder.add_node("report", report_node)

        # Edges — Supervisor routing
        builder.set_entry_point("intake")
        builder.add_edge("intake", "interview_planner")
        builder.add_edge("interview_planner", "planner_complete")
        # planner_complete forwards plan data to state, then routes to interviewer
        builder.add_edge("planner_complete", "interviewer")
        builder.add_edge("interviewer", "score")
        builder.add_conditional_edges(
            "score",
            self._route_after_score,
            {
                "interviewer": "interviewer",
                "report": "report",
            },
        )
        builder.add_edge("report", END)

        checkpointer = await get_checkpointer()
        return builder.compile(checkpointer=checkpointer, interrupt_before=["score"])

    def _route_after_score(self, state: InterviewGraphState) -> Literal["interviewer", "report"]:
        """Route to next question or report based on current_question count."""
        current = state.get("current_question", 0)
        if current < self.MAX_QUESTIONS:
            return "interviewer"
        return "report"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def start_interview(self) -> str:
        """Return a fresh thread_id for a new interview session."""
        return str(uuid4())

    async def submit_answer(
        self,
        thread_id: str,
        answer: str,
        sequence_no: int,
        user_id: str,
        *,
        position: str | None = None,
        company: str | None = None,
        branch_id: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Submit a user answer and advance the interview graph.

        First call: starts the graph from intake (no prior checkpoint). The
        session-level context (position/company/branch_id/job_id) is seeded
        into the initial state so the planner subgraph can read them without
        relying on the LLM to extract them from the user's free-text answer.

        Subsequent calls: updates state with the answer, then resumes from interrupt.
        """
        config = await get_graph_config(thread_id)

        # Check whether the graph has already started
        state = await retry_graph_op(self.build_graph, config, "aget_state")

        if state.values:
            # Graph has state — add answer and resume from interrupt
            await retry_graph_op(self.build_graph, config, "aupdate_state", {
                "messages": [{"role": "user", "content": answer, "sequence_no": sequence_no}],
            })
            result = await retry_graph_op(self.build_graph, config, "ainvoke", None, state_first=True)
        else:
            # First run — start the graph from the beginning. Seed
            # session-level context so downstream nodes (planner_context,
            # planner_generate, question_gen) can read position/company
            # without depending on intake's LLM extraction.
            initial_state: dict[str, Any] = {
                "messages": [{"role": "user", "content": answer, "sequence_no": sequence_no}],
                "user_id": user_id,
                "thread_id": thread_id,
            }
            if position:
                initial_state["position"] = position
            if company:
                initial_state["company"] = company
            if branch_id:
                initial_state["branch_id"] = branch_id
            if job_id:
                initial_state["job_id"] = job_id
            result = await retry_graph_op(
                self.build_graph, config, "ainvoke", initial_state, state_first=True
            )
        return result

    async def resume_from_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
        last_seen_checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Resume interview from a checkpoint.

        Returns the current state with next node information.
        """
        config = await get_graph_config(thread_id, checkpoint_ns)
        if last_seen_checkpoint_id:
            config["configurable"]["checkpoint_id"] = last_seen_checkpoint_id

        state = await retry_graph_op(self.build_graph, config, "aget_state")

        current_question = 0
        next_node = None
        if state.values:
            current_question = state.values.get("current_question", 0)
        if state.next:
            next_node = state.next

        return {
            "current_question": current_question,
            "next_node": next_node,
            "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id") if state.config else None,
            "values": state.values if state.values else {},
        }

    async def get_current_state(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
    ) -> dict[str, Any]:
        """Get the current graph state without advancing."""
        config = await get_graph_config(thread_id, checkpoint_ns)
        state = await retry_graph_op(self.build_graph, config, "aget_state")
        return {
            "current_question": state.values.get("current_question", 0) if state.values else 0,
            "values": state.values if state.values else {},
            "next": state.next if state.next else None,
        }


def _planner_complete_node(state: InterviewGraphState) -> dict:
    """After the planner subgraph finishes, forward plan data to interviewer.

    Explicitly propagates ``interview_plan`` and ``web_research`` from the
    subgraph output into the shared state so the ``interviewer`` node
    (question_gen) can read them.
    """
    return {
        "interview_plan": state.get("interview_plan"),
        "web_research": state.get("web_research"),
    }


# Singleton
_interview_graph: InterviewGraph | None = None


def get_interview_graph() -> InterviewGraph:
    global _interview_graph
    if _interview_graph is None:
        _interview_graph = InterviewGraph()
    return _interview_graph


__all__ = ["InterviewGraph", "get_interview_graph"]
