"""LangGraph resume_derive pipeline (REQ-055)."""
from __future__ import annotations

from typing import Any

from app.agents.nodes.resume_derive.calibrate_pages import calibrate_pages
from app.agents.nodes.resume_derive.draft_derived import draft_derived, select_materials
from app.agents.nodes.resume_derive.parse_jd import parse_jd
from app.agents.state.resume_derive_state import ResumeDeriveState


def run_resume_derive(state: ResumeDeriveState) -> ResumeDeriveState:
    """Execute derive pipeline synchronously (used by ARQ worker / CLI).

    Uses a linear node chain rather than requiring a compiled StateGraph
    so unit tests can run without checkpointer wiring. Production worker
    may wrap this in LangGraph later.
    """
    out: dict[str, Any] = dict(state)
    out.update(parse_jd(out))  # type: ignore[arg-type]
    out.update(select_materials(out))  # type: ignore[arg-type]
    out.update(draft_derived(out))  # type: ignore[arg-type]
    out.update(calibrate_pages(out))  # type: ignore[arg-type]
    return out  # type: ignore[return-value]


def build_resume_derive_graph():
    """Optional LangGraph compile for observability parity with other agents."""
    try:
        from langgraph.graph import END, StateGraph

        g = StateGraph(ResumeDeriveState)
        g.add_node("parse_jd", parse_jd)
        g.add_node("select_materials", select_materials)
        g.add_node("draft_derived", draft_derived)
        g.add_node("calibrate_pages", calibrate_pages)
        g.set_entry_point("parse_jd")
        g.add_edge("parse_jd", "select_materials")
        g.add_edge("select_materials", "draft_derived")
        g.add_edge("draft_derived", "calibrate_pages")
        g.add_edge("calibrate_pages", END)
        return g.compile()
    except Exception:
        return None
