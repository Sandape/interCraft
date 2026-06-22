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
from app.agents.checkpointer import get_graph_config
from app.agents.nodes.error_coach.evaluate import evaluate_node
from app.agents.nodes.error_coach.fetch_question import fetch_question_node
from app.agents.nodes.error_coach.hint_ladder import hint_ladder_node
from app.agents.nodes.error_coach.loop_or_finish import loop_or_finish_node
from app.agents.state.error_coach_state import ErrorCoachState
from app.services.error_coach_service import ErrorCoachService


class ErrorCoachGraph(BaseAgent):
    """LangGraph agent for error question reinforcement.

    Flow: fetch_question → hint_ladder ↔ evaluate ↔ loop_or_finish (3 rounds max)
    """

    def __init__(self) -> None:
        self._checkpointer = None

    async def _get_checkpointer(self):
        if self._checkpointer is None:
            from app.agents.checkpointer import get_checkpointer

            self._checkpointer = await get_checkpointer()
        return self._checkpointer

    async def build_graph(self) -> StateGraph:
        builder = StateGraph(ErrorCoachState)

        builder.add_node("fetch_question", fetch_question_node)
        builder.add_node("hint_ladder", hint_ladder_node)
        builder.add_node("evaluate", evaluate_node)
        builder.add_node("loop_or_finish", loop_or_finish_node)

        builder.set_entry_point("fetch_question")
        builder.add_edge("fetch_question", "hint_ladder")
        builder.add_edge("hint_ladder", "evaluate")
        builder.add_edge("evaluate", "loop_or_finish")
        builder.add_conditional_edges(
            "loop_or_finish",
            self._route_after_loop,
            {
                "hint_ladder": "hint_ladder",
                END: END,
            },
        )

        checkpointer = await self._get_checkpointer()
        # 021: pause after hint_ladder so the graph waits for the user's
        # next answer instead of looping evaluate→hint_ladder until the
        # recursion limit. Without this, start() runs the whole 3-round
        # conversation with itself and submit_answer is a no-op.
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_after=["hint_ladder"],
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
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        state = await graph.aget_state(config)
        if not state.values:
            return {"status": "not_found"}

        await graph.aupdate_state(config, {"messages": [{"role": "user", "content": content}]})
        result = await graph.ainvoke(None, config)

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
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        state = await graph.aget_state(config)
        # 021: if the graph is paused before evaluate (state.next contains
        # "evaluate"), skip it — we don't want to score the last answer a
        # second time during abort. Using as_node="evaluate" advances the
        # cursor past evaluate so ainvoke resumes at loop_or_finish.
        next_nodes = list(state.next or [])
        if "evaluate" in next_nodes:
            await graph.aupdate_state(
                config, {"session_aborted": True}, as_node="evaluate"
            )
        else:
            await graph.aupdate_state(config, {"session_aborted": True})
        result = await graph.ainvoke(None, config)

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
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)
        state = await graph.aget_state(config)

        values = state.values or {}
        return {
            "thread_id": thread_id,
            "status": "completed" if not state.next else "running",
            "correct_count": values.get("correct_count", 0),
            "attempt_count": values.get("attempt_count", 0),
            "current_hint_level": values.get("current_hint_level", "small"),
        }


_error_coach_graph: ErrorCoachGraph | None = None


def get_error_coach_graph() -> ErrorCoachGraph:
    global _error_coach_graph
    if _error_coach_graph is None:
        _error_coach_graph = ErrorCoachGraph()
    return _error_coach_graph


__all__ = ["ErrorCoachGraph", "get_error_coach_graph"]
