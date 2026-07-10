"""Eval: JD keyword present in root → material included (REQ-055)."""
from __future__ import annotations

from app.agents.nodes.resume_derive.draft_derived import draft_derived, select_materials


def test_select_materials_includes_jd_match():
    state = {
        "jd_parse": {"priority_high": ["python", "rag"]},
        "root_data": {
            "sections": {
                "projects": {
                    "items": [
                        {"id": "p1", "name": "RAG", "bullets": ["Built RAG with Python"]},
                        {"id": "p2", "name": "Blog", "bullets": ["Wrote posts"]},
                    ]
                }
            }
        },
    }
    out = select_materials(state)  # type: ignore[arg-type]
    included_refs = {e["ref"] for e in out["selection_plan"]["included"]}
    assert "root:projects:p1" in included_refs
    assert "root:projects:p2" not in included_refs


def test_draft_keeps_included_material_in_derived_sections():
    state = {
        "root_data": {
            "basics": {"name": "Ada"},
            "sections": {
                "projects": {
                    "items": [
                        {"id": "p1", "name": "RAG", "bullets": ["Python RAG pipeline"]},
                    ]
                }
            },
            "metadata": {},
        },
        "selection_plan": {
            "included": [{"ref": "root:projects:p1", "section": "projects", "score": +2}],
            "compressed": [],
            "hidden": [],
        },
        "jd_parse": {"priority_high": ["python", "rag"], "evidence_missing": []},
        "job_position": "AI Engineer",
    }
    out = draft_derived(state)  # type: ignore[arg-type]
    items = out["derived_data"]["sections"]["projects"]["items"]
    assert len(items) == 1
    assert items[0]["name"] == "RAG"
    assert "root:projects:p1" in items[0].get("source_refs", [])
