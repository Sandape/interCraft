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


class GeneralCoachGraph(BaseAgent):
    """LangGraph agent for general coaching conversations.

    Flow: intent → route → respond → END
    """

    async def build_graph(self) -> StateGraph:
        builder = StateGraph(GeneralCoachState)

        builder.add_node("intent", intent_node)
        builder.add_node("route", route_node)
        builder.add_node("respond", respond_node)

        builder.set_entry_point("intent")
        builder.add_edge("intent", "route")
        builder.add_edge("route", "respond")
        builder.add_edge("respond", END)

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
        return {
            "thread_id": thread_id,
            "detected_intent": values.get("detected_intent"),
            "message_count": len(values.get("messages", [])),
            "session_active": values.get("session_active", False),
        }


_general_coach_graph: GeneralCoachGraph | None = None


def get_general_coach_graph() -> GeneralCoachGraph:
    global _general_coach_graph
    if _general_coach_graph is None:
        _general_coach_graph = GeneralCoachGraph()
    return _general_coach_graph


__all__ = ["GeneralCoachGraph", "get_general_coach_graph"]
