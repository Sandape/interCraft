"""Unit tests for source validator (REQ-055 anti-fabrication)."""
from __future__ import annotations

from app.agents.nodes.resume_derive.validate_sources import collect_root_refs, validate_sources


def test_validate_sources_drops_unreferenced_claims():
    root = {
        "sections": {
            "projects": {
                "items": [{"id": "p1", "name": "RAG", "bullets": ["built evals"]}]
            }
        }
    }
    allowed = collect_root_refs(root)
    derived = {
        "sections": {
            "projects": {
                "items": [
                    {
                        "id": "ok",
                        "name": "RAG",
                        "source_refs": ["root:projects:p1"],
                        "bullets": ["built evals"],
                    },
                    {
                        "id": "bad",
                        "name": "Fake",
                        "source_refs": ["root:projects:missing"],
                        "bullets": ["invented"],
                    },
                    {
                        "id": "noref",
                        "name": "Also fake",
                        "bullets": ["no refs"],
                    },
                ]
            }
        },
        "metadata": {"derive": {}},
    }
    out = validate_sources(derived, allowed_refs=allowed)
    items = out["sections"]["projects"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == "ok"
    assert out["metadata"]["derive"]["rejectedClaims"]


def test_eval_missing_skill_not_in_body_when_no_evidence():
    from app.agents.graphs.resume_derive import run_resume_derive

    state = {
        "jd_text": "Require deep LLM Evals experience and Agent evaluation harness.",
        "job_position": "AI Engineer",
        "job_company": "Acme",
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
        "target_page_count": 1,
        "template_id": "pikachu",
        "calibrate_round": 0,
    }
    result = run_resume_derive(state)  # type: ignore[arg-type]
    blob = str(result.get("derived_data")).lower()
    # Must not claim possessing LLM Evals as fact in body without evidence
    assert "具备完整 llm evals" not in blob
    questions = result.get("supplement_questions") or []
    assert any("eval" in str(q).lower() for q in questions)
