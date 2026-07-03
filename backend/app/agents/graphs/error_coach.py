"""M17 Error Coach StateGraph — LangGraph agent for error question reinforcement.

Graph structure:
    fetch_question → hint_ladder → {wait_user → evaluate → loop_or_finish} (cycle)

Ends when correct_count >= 3 or session_aborted.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.nodes.error_coach.evaluate import evaluate_node
from app.agents.nodes.error_coach.fetch_question import fetch_question_node
from app.agents.nodes.error_coach.hint_ladder import hint_ladder_node
from app.agents.nodes.error_coach.loop_or_finish import loop_or_finish_node
from app.agents.state.error_coach_state import ErrorCoachState
from app.observability import traced_node
from app.services.error_coach_service import ErrorCoachService


# ---------------------------------------------------------------------------
# US2 AC-3.4 / AC-E2E-5: re-decorated shims with `__name__` matching the
# {role}_{action} suffix so the add_node registration name and the
# function `__name__` align. The underlying implementation still lives in
# the leaf module (and is still importable as ``*_node`` for backward
# compat with external callers like ``app.eval.runner``).
# ---------------------------------------------------------------------------


@traced_node("error_coach.fetch_question")
async def fetch_question(state: Any) -> Any:
    return await fetch_question_node(state)


@traced_node("error_coach.hint_ladder")
async def hint_ladder(state: Any) -> Any:
    return await hint_ladder_node(state)


@traced_node("error_coach.evaluate")
async def evaluate(state: Any) -> Any:
    return await evaluate_node(state)


@traced_node("error_coach.loop_or_finish")
async def loop_or_finish(state: Any) -> Any:
    return await loop_or_finish_node(state)


class ErrorCoachGraph(BaseAgent):
    """LangGraph agent for error question reinforcement.

    Flow: fetch_question → hint_ladder ↔ evaluate ↔ loop_or_finish (3 rounds max)
    """

    async def build_graph(self) -> StateGraph:
        builder = StateGraph(ErrorCoachState)

        # US2 FR-003 / AC-3.4: node names follow `{agent}.{role}_{action}`.
        builder.add_node("error_coach.fetch_question", fetch_question)
        builder.add_node("error_coach.hint_ladder", hint_ladder)
        builder.add_node("error_coach.evaluate", evaluate)
        builder.add_node("error_coach.loop_or_finish", loop_or_finish)

        builder.set_entry_point("error_coach.fetch_question")
        builder.add_edge("error_coach.fetch_question", "error_coach.hint_ladder")
        builder.add_edge("error_coach.hint_ladder", "error_coach.evaluate")
        builder.add_edge("error_coach.evaluate", "error_coach.loop_or_finish")
        builder.add_conditional_edges(
            "error_coach.loop_or_finish",
            self._route_after_loop,
            {
                "hint_ladder": "error_coach.hint_ladder",
                END: END,
            },
        )

        checkpointer = await get_checkpointer()
        # 021: pause after hint_ladder so the graph waits for the user's
        # next answer instead of looping evaluate→hint_ladder until the
        # recursion limit. Without this, start() runs the whole 3-round
        # conversation with itself and submit_answer is a no-op.
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_after=["error_coach.hint_ladder"],
        )

    def _route_after_loop(self, state: ErrorCoachState) -> Literal["hint_ladder", "__end__"]:
        correct_count = state.get("correct_count", 0)
        session_aborted = state.get("session_aborted", False)
        if correct_count >= 3 or session_aborted:
            return END
        return "hint_ladder"

    async def start(self, user_id: str, error_question_id: str) -> str:
        thread_id = str(uuid4())
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        await graph.ainvoke(
            {
                "user_id": user_id,
                "error_question_id": error_question_id,
                "correct_count": 0,
                "attempt_count": 0,
                "current_hint_level": "small",
                "session_aborted": False,
                "thread_id": thread_id,
            },
            config,
        )
        return thread_id

    async def submit_answer(self, thread_id: str, content: str) -> dict[str, Any]:
        config = await get_graph_config(thread_id)

        state = await retry_graph_op(self.build_graph, config, "aget_state")
        if not state.values:
            return {"status": "not_found"}

        await retry_graph_op(self.build_graph, config, "aupdate_state", {"messages": [{"role": "user", "content": content}]})
        result = await retry_graph_op(self.build_graph, config, "ainvoke", None, state_first=True)

        # If session complete, decrement frequency
        correct_count = result.get("correct_count", 0)
        session_aborted = result.get("session_aborted", False)
        if correct_count >= 3 or session_aborted:
            user_id = state.values.get("user_id", "")
            error_question_id = state.values.get("error_question_id", "")
            if error_question_id and user_id:
                service = ErrorCoachService()
                await service.decrement_frequency(error_question_id, user_id)

        return result

    async def abort(self, thread_id: str) -> dict[str, Any]:
        config = await get_graph_config(thread_id)

        state = await retry_graph_op(self.build_graph, config, "aget_state")
        # 021: if the graph is paused before evaluate (state.next contains
        # "evaluate"), skip it — we don't want to score the last answer a
        # second time during abort. Using as_node="evaluate" advances the
        # cursor past evaluate so ainvoke resumes at loop_or_finish.
        next_nodes = list(state.next or [])
        if "error_coach.evaluate" in next_nodes:
            await retry_graph_op(self.build_graph, config, "aupdate_state", {"session_aborted": True}, as_node="error_coach.evaluate")
        else:
            await retry_graph_op(self.build_graph, config, "aupdate_state", {"session_aborted": True})
        result = await retry_graph_op(self.build_graph, config, "ainvoke", None, state_first=True)

        # 021: abort must also decrement frequency (mirrors submit_answer's
        # end-of-session path). Without this, an abandoned session leaves
        # frequency unchanged.
        session_aborted = result.get("session_aborted", False)
        if session_aborted:
            user_id = (state.values or {}).get("user_id", "")
            error_question_id = (state.values or {}).get("error_question_id", "")
            if error_question_id and user_id:
                service = ErrorCoachService()
                await service.decrement_frequency(error_question_id, user_id)

        return result

    async def get_state(self, thread_id: str) -> dict[str, Any]:
        config = await get_graph_config(thread_id)
        state = await retry_graph_op(self.build_graph, config, "aget_state")

        values = state.values or {}
        # AC-3.7a: surface typed ``error`` for ``serialize_state_error``
        # in the API layer (SC-002 fill-rate contract).
        error_payload = values.get("error")
        return {
            "thread_id": thread_id,
            "status": "completed" if not state.next else "running",
            "correct_count": values.get("correct_count", 0),
            "attempt_count": values.get("attempt_count", 0),
            "current_hint_level": values.get("current_hint_level", "small"),
            "error": error_payload,
        }


_error_coach_graph: ErrorCoachGraph | None = None


def get_error_coach_graph() -> ErrorCoachGraph:
    global _error_coach_graph
    if _error_coach_graph is None:
        _error_coach_graph = ErrorCoachGraph()
    return _error_coach_graph


__all__ = ["ErrorCoachGraph", "get_error_coach_graph"]
