"""Unit tests for reply_formatter."""

from app.modules.agent.conversation.reply_formatter import (
    HELP_TEXT,
    format_confirmation_card,
    format_create_job_card,
    format_low_confidence,
    format_update_status_card,
    segment,
    truncate,
)


def test_truncate():
    assert truncate("短") == "短"
    long = "x" * 600
    out = truncate(long, 50)
    assert len(out) == 50
    assert out.endswith("…")


def test_segment_uses_split():
    text = "第一段\n\n" + ("很长内容" * 80)
    parts = segment(text, max_len=100)
    assert isinstance(parts, list)
    assert len(parts) >= 1


def test_confirmation_card():
    card = format_confirmation_card("新增岗位", "📮 腾讯 · 后端")
    assert "即将新增岗位" in card
    assert "确认" in card
    assert "取消" in card


def test_create_and_status_cards():
    c = format_create_job_card({"company": "字节", "position": "前端", "base_location": "北京"})
    assert "字节" in c and "前端" in c and "北京" in c

    s = format_update_status_card(
        {
            "company": "字节",
            "position": "前端",
            "target_status": "interview_1",
            "interview_time_display": "7月10日 14:00",
        }
    )
    assert "一面" in s
    assert "7月10日" in s


def test_low_confidence_and_help():
    text = format_low_confidence(
        [{"intent": "create_job", "confidence": 0.4}, {"intent": "query_jobs", "confidence": 0.3}]
    )
    assert "新增岗位" in text
    assert "帮助" in HELP_TEXT or "岗位" in HELP_TEXT
