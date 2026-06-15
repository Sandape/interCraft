"""InterviewGraph — LangGraph StateGraph for interview flow (T029).

Graph structure:
    intake → question_gen → score → (condition: current_question < 5 → question_gen, else → report)

Uses PostgreSQL checkpointer for state persistence.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_graph_config
from app.agents.interview.nodes.intake import intake_node
from app.agents.interview.nodes.question_gen import question_gen_node
from app.agents.interview.nodes.report import report_node
from app.agents.interview.nodes.score import score_node
from app.agents.interview.state import InterviewGraphState


class InterviewGraph(BaseAgent):
    """LangGraph agent for AI-powered mock interviews.

    Flow: intake -> question_gen <-> score (x5) -> report
    """

    MAX_QUESTIONS = 5

    def __init__(self) -> None:
        self._checkpointer = None

    async def _get_checkpointer(self):
        if self._checkpointer is None:
            from app.agents.checkpointer import get_checkpointer

            self._checkpointer = await get_checkpointer()
        return self._checkpointer

    async def _is_checkpointer_alive(self) -> bool:
        """Probe the checkpointer's underlying psycopg connection.

        AsyncPostgresSaver's pooled connection can go silent (the kernel
        closes an idle TCP socket but psycopg doesn't notice until the
        next query). Catch that here so resume/aget_state can rebuild
        instead of returning 500.
        """
        cp = await self._get_checkpointer()
        conn = getattr(cp, "conn", None) or getattr(cp, "_conn", None)
        if conn is None or conn.closed:
            return False
        try:
            await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def _rebuild_checkpointer(self) -> None:
        """Discard the cached checkpointer so the next call rebuilds it.

        The previous AsyncPostgresSaver is closed best-effort; on any
        error we just drop our reference and let GC handle it.
        """
        from app.agents.checkpointer import close_checkpointer

        self._checkpointer = None
        try:
            await close_checkpointer()
        except Exception:
            pass

    async def aget_state_with_retry(self, thread_id: str, checkpoint_ns: str = ""):
        """aget_state that rebuilds the checkpointer on connection loss.

        The first query after idle fails with `psycopg.OperationalError:
        the connection is closed`; rebuilding the checkpointer forces a
        fresh psycopg connection and the second attempt succeeds.
        """
        from app.agents.checkpointer import get_graph_config

        last_exc: Exception | None = None
        for attempt in range(2):
            graph = await self.build_graph()
            config = await get_graph_config(thread_id, checkpoint_ns)
            try:
                return await graph.aget_state(config)
            except Exception as exc:
                msg = str(exc).lower()
                is_conn_dead = (
                    "connection is closed" in msg
                    or "closed the connection" in msg
                    or "admin shutdown" in msg  # pg_terminate_backend
                )
                if not is_conn_dead or attempt == 1:
                    raise
                last_exc = exc
                await self._rebuild_checkpointer()
        # Unreachable, but keeps the type checker happy
        raise last_exc  # type: ignore[misc]

    async def build_graph(self) -> StateGraph:
        """Build the compiled interview StateGraph with PostgreSQL checkpointer."""
        builder = StateGraph(InterviewGraphState)

        # Add nodes
        builder.add_node("intake", intake_node)
        builder.add_node("question_gen", question_gen_node)
        builder.add_node("score", score_node)
        builder.add_node("report", report_node)

        # Edges
        builder.set_entry_point("intake")
        builder.add_edge("intake", "question_gen")
        builder.add_edge("question_gen", "score")
        builder.add_conditional_edges(
            "score",
            self._route_after_score,
            {
                "question_gen": "question_gen",
                "report": "report",
            },
        )
        builder.add_edge("report", END)

        checkpointer = await self._get_checkpointer()
        return builder.compile(checkpointer=checkpointer, interrupt_before=["score"])

    def _route_after_score(self, state: InterviewGraphState) -> Literal["question_gen", "report"]:
        """Route to next question or report based on current_question count."""
        current = state.get("current_question", 0)
        if current < self.MAX_QUESTIONS:
            return "question_gen"
        return "report"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def start_interview(
        self,
        session_id: str,
        user_id: str,
        position: str,
        company: str,
        difficulty: str = "medium",
        branch_id: str | None = None,
    ) -> str:
        """Initialize an interview session and return the thread_id."""
        thread_id = str(uuid4())
        return thread_id

    async def submit_answer(
        self,
        thread_id: str,
        answer: str,
        sequence_no: int,
        user_id: str,
    ) -> dict[str, Any]:
        """Submit a user answer and advance the interview graph.

        First call: starts the graph from intake (no prior checkpoint).
        Subsequent calls: updates state with the answer, then resumes from interrupt.
        """
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        # Check whether the graph has already started
        state = await graph.aget_state(config)

        if state.values:
            # Graph has state — add answer and resume from interrupt
            await graph.aupdate_state(
                config,
                {
                    "messages": [{"role": "user", "content": answer, "sequence_no": sequence_no}],
                },
            )
            result = await graph.ainvoke(None, config)
        else:
            # First run — start the graph from the beginning
            result = await graph.ainvoke(
                {
                    "messages": [{"role": "user", "content": answer, "sequence_no": sequence_no}],
                    "user_id": user_id,
                    "thread_id": thread_id,
                },
                config,
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
        from app.agents.checkpointer import get_graph_config

        config = await get_graph_config(thread_id, checkpoint_ns)
        if last_seen_checkpoint_id:
            config["configurable"]["checkpoint_id"] = last_seen_checkpoint_id

        state = await self.aget_state_with_retry(thread_id, checkpoint_ns)

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
        state = await self.aget_state_with_retry(thread_id, checkpoint_ns)
        return {
            "current_question": state.values.get("current_question", 0) if state.values else 0,
            "values": state.values if state.values else {},
            "next": state.next if state.next else None,
        }


# Singleton
_interview_graph: InterviewGraph | None = None


def get_interview_graph() -> InterviewGraph:
    global _interview_graph
    if _interview_graph is None:
        _interview_graph = InterviewGraph()
    return _interview_graph


__all__ = ["InterviewGraph", "get_interview_graph"]
