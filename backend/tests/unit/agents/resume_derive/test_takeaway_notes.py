"""Unit tests for draft_derived takeaway_notes (REQ-055)."""
from __future__ import annotations

from app.agents.nodes.resume_derive.draft_derived import draft_derived


def _base_state(**overrides):
    state = {
        "root_data": {
            "basics": {"name": "Ada"},
            "summary": {"content": "Backend engineer"},
            "sections": {
                "projects": {
                    "items": [
                        {
                            "id": "p1",
                            "name": "RAG",
                            "bullets": ["Built Python APIs with LLM evals"],
                        }
                    ]
                }
            },
            "metadata": {},
        },
        "selection_plan": {
            "included": [{"ref": "root:projects:p1", "section": "projects", "score": 1}],
            "compressed": [],
            "hidden": [],
            "must_show": ["basics", "summary"],
        },
        "jd_parse": {
            "priority_high": ["python", "llm"],
            "evidence_missing": ["kubernetes"],
        },
        "job_position": "AI Engineer",
    }
    state.update(overrides)
    return state


def test_draft_derived_emits_takeaway_notes():
    out = draft_derived(_base_state())  # type: ignore[arg-type]
    notes = out.get("takeaway_notes") or []
    assert isinstance(notes, list)
    assert len(notes) >= 2
    joined = " ".join(notes)
    assert "JD" in joined or "素材" in joined
    assert any("kubernetes" in n for n in notes)
