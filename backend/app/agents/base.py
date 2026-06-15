"""BaseAgent ABC + GraphState TypedDict + NodeResult dataclass (T012).

Foundation for all LangGraph agent subgraphs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Annotated, Any

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    """Base graph state with message accumulation.

    All subgraph states extend this with domain-specific fields.
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    thread_id: str
    user_id: str
    request_id: str


@dataclass
class NodeResult:
    """Result of a single node execution."""

    node_name: str
    status: str  # "success" | "error" | "quota_exceeded"
    output: dict[str, Any] = field(default_factory=dict)
    checkpoint_id: str | None = None
    duration_ms: int = 0


class BaseAgent(ABC):
    """Abstract base for LangGraph agents.

    Subclasses implement build_graph() returning a compiled StateGraph.
    """

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build and return the compiled StateGraph."""
        ...

    async def ainvoke(self, state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke the graph with the given state and config."""
        graph = self.build_graph()
        result = await graph.ainvoke(state, config=config)
        return result


__all__ = ["BaseAgent", "GraphState", "NodeResult"]
