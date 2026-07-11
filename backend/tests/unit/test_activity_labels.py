"""Unit tests for dashboard activity Chinese labels (REQ-057)."""
from __future__ import annotations

from app.modules.dashboard.activity_labels import render_activity


def test_job_created_title_zh():
    title, detail, href = render_activity(
        "job_created",
        {"job_id": "abc", "company": "字节", "position": "后端"},
    )
    assert title == "新增投递"
    assert "字节" in detail
    assert href == "/jobs/abc"


def test_job_status_changed_title_zh():
    title, detail, _ = render_activity(
        "job_status_changed",
        {"company": "A", "position": "B", "to_status": "interview_1"},
    )
    assert title == "岗位状态更新"
    assert "一面" in detail


def test_unknown_type_neutral_zh():
    title, detail, href = render_activity("totally_unknown_event", {})
    assert title == "系统更新"
    assert title != "totally_unknown_event"
    assert href is None


def test_never_uses_raw_type_for_known():
    for t in (
        "job_created",
        "task_completed",
        "interview_completed",
        "error_logged",
    ):
        title, _, _ = render_activity(t, {})
        assert title != t


def test_completed_interview_activity_opens_report_not_live_session():
    _, _, href = render_activity(
        "interview_completed",
        {"session_id": "session-1", "company": "A", "position": "B"},
    )

    assert href == "/interview/session-1/report"
