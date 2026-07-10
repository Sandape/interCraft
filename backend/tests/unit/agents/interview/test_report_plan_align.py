"""Report plan alignment (REQ-058 T046)."""
from __future__ import annotations

import pytest

from app.agents.interview.nodes.report import _fallback_report, _normalize_report, report_node


def test_report_length_matches_n_and_no_five_round() -> None:
    scores = [
        {"question_no": i, "dimension": "tech_depth", "score": 7, "feedback": "ok"}
        for i in range(1, 11)
    ]
    questions = [{"question": f"Q{i}"} for i in range(1, 11)]
    report = _fallback_report(
        scores,
        questions,
        focus_areas=[{"area": "分布式", "weight": 0.5}],
    )
    assert len(report["per_question_score"]) == 10
    assert report["overall_score"] == 7.0
    assert "五轮" not in report["summary_md"]
    assert "10" in report["summary_md"]
    assert any("分布式" in s for item in report["improvements"] for s in item["suggestions"])


def test_normalize_scrubs_five_round_copy() -> None:
    scores = [{"question_no": 1, "dimension": "a", "score": 6, "feedback": ""}] * 3
    questions = [{"question": "q"}] * 3
    normalized = _normalize_report(
        {"summary_md": "本次五轮面试表现一般", "overall_score": 9},
        scores,
        questions,
    )
    assert "五轮" not in normalized["summary_md"]
    assert normalized["overall_score"] == 6.0
    assert len(normalized["per_question_score"]) == 3


@pytest.mark.asyncio
async def test_degraded_report_uses_rule_summary_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> object:
        raise AssertionError("degraded report path must not call LLM")

    monkeypatch.setattr(
        "app.agents.interview.nodes.report.get_llm_client",
        fail_if_called,
    )
    scores = [
        {
            "question_no": i,
            "dimension": "tech_depth" if i % 2 else "algorithm",
            "score": 9 if i % 2 else 4,
            "feedback": "ok",
            "scoring_method": "local_degraded_template",
        }
        for i in range(1, 11)
    ]
    questions = [{"question": f"Q{i}"} for i in range(1, 11)]

    out = await report_node({"scores": scores, "questions": questions, "degraded": True})

    report = out["interview_report"]
    assert out["overall_score"] == 6.5
    assert len(report["per_question_score"]) == 10
    assert report["report_source"] == "local_degraded"
