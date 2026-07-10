"""Eval: root lacks evidence → derived body must not claim it (REQ-055)."""
from __future__ import annotations

from app.agents.nodes.resume_derive.draft_derived import draft_derived


def test_missing_jd_skill_not_fabricated_in_derived_body():
    state = {
        "root_data": {
            "basics": {"name": "Ada"},
            "summary": {"content": "Backend engineer"},
            "sections": {
                "projects": {
                    "items": [
                        {
                            "id": "p1",
                            "name": "Payment API",
                            "bullets": ["Built REST APIs in Python"],
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
        },
        "jd_parse": {
            "priority_high": ["kubernetes"],
            "evidence_missing": ["kubernetes"],
        },
        "job_position": "Platform Engineer",
    }
    out = draft_derived(state)  # type: ignore[arg-type]
    derived = out["derived_data"]
    sections = derived.get("sections") or {}
    summary = (derived.get("summary") or {}).get("content") or ""
    md = ((derived.get("metadata") or {}).get("markdown") or {}).get("sourceMarkdown") or ""
    body = f"{sections} {summary} {md}".lower()
    assert "kubernetes" not in body
    questions = out.get("supplement_questions") or []
    assert any("kubernetes" in str(q).lower() for q in questions)
