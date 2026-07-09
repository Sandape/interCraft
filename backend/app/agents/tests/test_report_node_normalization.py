from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_report_node_backfills_partial_llm_report(monkeypatch) -> None:
    from app.agents.interview.nodes import report

    class FakeClient:
        async def invoke(self, **kwargs):
            return {"content": '{"overall_score": 0}'}

    monkeypatch.setattr(report, "get_llm_client", lambda: FakeClient())

    result = await report.report_node(
        {
            "position": "Software Engineer",
            "company": "Example",
            "difficulty": "medium",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "thread_id": "thread-1",
            "questions": [
                {"question": "Q1", "dimension": "tech_depth"},
                {"question": "Q2", "dimension": "architecture"},
            ],
            "scores": [
                {
                    "question_no": 1,
                    "dimension": "tech_depth",
                    "score": 4,
                    "feedback": "Needs more depth",
                    "user_answer": "A1",
                },
                {
                    "question_no": 2,
                    "dimension": "architecture",
                    "score": 8,
                    "feedback": "Good tradeoffs",
                    "user_answer": "A2",
                },
            ],
        }
    )

    report_data = result["interview_report"]
    assert result["overall_score"] == 6.0
    assert report_data["overall_score"] == 6.0
    assert len(report_data["per_question_score"]) == 2
    assert report_data["per_question_score"][0]["question_text"] == "Q1"
    assert report_data["per_question_score"][1]["user_answer"] == "A2"
    assert report_data["dimension_scores"] == {"tech_depth": 4.0, "architecture": 8.0}
