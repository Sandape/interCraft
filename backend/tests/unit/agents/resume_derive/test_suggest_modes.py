"""Unit tests for suggestion apply_mode classification (REQ-055)."""
from __future__ import annotations

from app.agents.nodes.resume_derive.draft_derived import draft_derived

ALLOWED_APPLY_MODES = {"direct", "needs_supplement", "do_not_write", "ask", "manual"}


def test_draft_suggestions_include_apply_mode():
    state = {
        "root_data": {
            "basics": {"name": "Ada"},
            "sections": {
                "projects": {
                    "items": [{"id": "p1", "name": "API", "bullets": ["Python REST"]}]
                }
            },
            "metadata": {},
        },
        "selection_plan": {
            "included": [{"ref": "root:projects:p1", "section": "projects", "score": 1}],
            "compressed": [],
            "hidden": [],
        },
        "jd_parse": {
            "priority_high": ["python"],
            "evidence_missing": ["kubernetes"],
        },
        "job_position": "Backend",
    }
    out = draft_derived(state)  # type: ignore[arg-type]
    suggestions = out.get("suggestions") or []
    assert suggestions, "expected at least one suggestion"
    for s in suggestions:
        assert "apply_mode" in s
        assert s["apply_mode"] in ALLOWED_APPLY_MODES


def test_data_gap_suggestions_use_needs_supplement():
    state = {
        "root_data": {"basics": {"name": "Ada"}, "sections": {}, "metadata": {}},
        "selection_plan": {"included": [], "compressed": [], "hidden": []},
        "jd_parse": {"priority_high": ["rag"], "evidence_missing": ["rag"]},
        "job_position": "ML Engineer",
    }
    out = draft_derived(state)  # type: ignore[arg-type]
    gap_suggestions = [s for s in out.get("suggestions") or [] if s.get("type") == "data_gap"]
    assert gap_suggestions
    assert all(s.get("apply_mode") == "needs_supplement" for s in gap_suggestions)
