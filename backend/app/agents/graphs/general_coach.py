"""M19 General Coach StateGraph — LangGraph agent for general coaching.

Graph structure:
    intent → route → respond → END (or redirect)

Supports streaming responses via WS for non-redirect intents.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.nodes.general_coach.intent import intent_node
from app.agents.nodes.general_coach.respond import respond_node
from app.agents.nodes.general_coach.route import route_node
from app.agents.state.general_coach_state import GeneralCoachState
from app.observability import traced_node


# US2 AC-3.4 / AC-E2E-5: re-decorated shims with `__name__` matching the
# {role}_{action} suffix.
@traced_node("general_coach.intent")
async def intent(state: Any) -> Any:
    return await intent_node(state)


@traced_node("general_coach.route")
async def route(state: Any) -> Any:
    return await route_node(state)


@traced_node("general_coach.respond")
async def respond(state: Any) -> Any:
    return await respond_node(state)


class GeneralCoachGraph(BaseAgent):
    """LangGraph agent for general coaching conversations.

    Flow: intent → route → respond → END
    """

    async def build_graph(self) -> StateGraph:
        builder = StateGraph(GeneralCoachState)

        # US2 FR-003 / AC-3.4: node names follow `{agent}.{role}_{action}`.
        builder.add_node("general_coach.intent", intent)
        builder.add_node("general_coach.route", route)
        builder.add_node("general_coach.respond", respond)

        builder.set_entry_point("general_coach.intent")
        builder.add_edge("general_coach.intent", "general_coach.route")
        builder.add_edge("general_coach.route", "general_coach.respond")
        builder.add_edge("general_coach.respond", END)

        checkpointer = await get_checkpointer()
        return builder.compile(checkpointer=checkpointer)

    async def start(self, user_id: str, initial_question: str = "") -> str:
        thread_id = str(uuid4())
        graph = await self.build_graph()
        config = await get_graph_config(thread_id)

        messages = []
        if initial_question:
            messages.append({"role": "user", "content": initial_question})

        await graph.ainvoke(
            {
                "user_id": user_id,
                "conversation_id": thread_id,
                "detected_intent": None,
                "confidence": None,
                "suggested_redirect": None,
                "session_active": True,
                "thread_id": thread_id,
                "messages": messages,
            },
            config,
        )
        return thread_id

    async def send_message(self, thread_id: str, content: str) -> dict[str, Any]:
        config = await get_graph_config(thread_id)

        await retry_graph_op(self.build_graph, config, "aupdate_state", {"messages": [{"role": "user", "content": content}]})
        result = await retry_graph_op(self.build_graph, config, "ainvoke", None, state_first=True)
        return result

    async def close(self, thread_id: str) -> None:
        config = await get_graph_config(thread_id)
        await retry_graph_op(self.build_graph, config, "aupdate_state", {"session_active": False})

    async def get_state(self, thread_id: str) -> dict[str, Any]:
        config = await get_graph_config(thread_id)
        state = await retry_graph_op(self.build_graph, config, "aget_state")
        values = state.values or {}
        # REQ-041 AC-3.7a: surface the typed ``error`` envelope to the API
        # layer so ``serialize_state_error`` can project it into the
        # ``error_category`` / ``node_name`` / ``cause`` HTTP fields.
        error_payload = values.get("error")
        return {
            "thread_id": thread_id,
            "detected_intent": values.get("detected_intent"),
            "message_count": len(values.get("messages", [])),
            "session_active": values.get("session_active", False),
            "error": error_payload,
        }


_general_coach_graph: GeneralCoachGraph | None = None


def get_general_coach_graph() -> GeneralCoachGraph:
    global _general_coach_graph
    if _general_coach_graph is None:
        _general_coach_graph = GeneralCoachGraph()
    return _general_coach_graph


__all__ = ["GeneralCoachGraph", "get_general_coach_graph"]
