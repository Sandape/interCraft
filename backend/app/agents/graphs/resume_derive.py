"""REQ-059 real-AI LangGraph plus deterministic fixture adapter."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.nodes.resume_derive.calibrate_pages import calibrate_pages
from app.agents.nodes.resume_derive.draft_derived import (
    draft_derived,
    draft_derived_ai,
    select_materials,
)
from app.agents.nodes.resume_derive.map_evidence import map_evidence_ai
from app.agents.nodes.resume_derive.parse_jd import parse_jd, parse_jd_ai
from app.agents.state.resume_derive_state import ResumeDeriveState


def _build_real_graph():
    graph = StateGraph(ResumeDeriveState)
    graph.add_node("parse_jd", parse_jd_ai)
    graph.add_node("map_evidence", map_evidence_ai)
    graph.add_node("select_materials", select_materials)
    graph.add_node("draft_derived", draft_derived_ai)
    graph.add_node("calibrate_pages", calibrate_pages)
    graph.set_entry_point("parse_jd")
    graph.add_edge("parse_jd", "map_evidence")
    graph.add_edge("map_evidence", "select_materials")
    graph.add_edge("select_materials", "draft_derived")
    graph.add_edge("draft_derived", "calibrate_pages")
    graph.add_edge("calibrate_pages", END)
    return graph.compile()


_REAL_GRAPH = _build_real_graph()


async def run_resume_derive_async(state: ResumeDeriveState) -> ResumeDeriveState:
    """Production path: every semantic node calls the centralized provider."""
    result = await _REAL_GRAPH.ainvoke(dict(state))
    return result  # type: ignore[return-value]


def run_resume_derive(state: ResumeDeriveState) -> ResumeDeriveState:
    """Deterministic fixture adapter retained for isolated legacy unit tests.

    The worker never calls this adapter, so its output cannot be exposed as a
    real AI result.
    """
    out: dict[str, Any] = dict(state)
    out.update(parse_jd(out))  # type: ignore[arg-type]
    out.update(select_materials(out))  # type: ignore[arg-type]
    out.update(draft_derived(out))  # type: ignore[arg-type]
    out.update(calibrate_pages(out))  # type: ignore[arg-type]
    return out  # type: ignore[return-value]


def build_resume_derive_graph():
    return _REAL_GRAPH
