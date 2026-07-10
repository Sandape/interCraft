"""Unit tests for interview completion detection helper."""
from __future__ import annotations

from app.modules.interviews.completion import is_interview_graph_complete


def test_complete_when_interview_report_present() -> None:
    assert is_interview_graph_complete(
        {"scores": [{"score": 7}] * 3, "interview_report": {"summary_md": "ok"}}
    )


def test_not_complete_on_five_scores_alone() -> None:
    # Regression: full mode must NOT complete at len(scores)==5.
    assert not is_interview_graph_complete({"scores": [{"score": 8}] * 5})


def test_complete_when_status_completed() -> None:
    assert is_interview_graph_complete({"status": "completed", "scores": []})


def test_not_complete_on_empty_or_none() -> None:
    assert not is_interview_graph_complete(None)
    assert not is_interview_graph_complete({})
    assert not is_interview_graph_complete({"interview_report": {}})
    assert not is_interview_graph_complete({"interview_report": None})
