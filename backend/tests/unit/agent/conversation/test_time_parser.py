"""Unit tests for Asia/Shanghai relative time parser."""

from datetime import datetime

from app.modules.agent.conversation.time_parser import (
    SHANGHAI,
    format_shanghai,
    parse_relative_time,
)


def test_tomorrow_afternoon():
    now = datetime(2026, 7, 9, 10, 0, tzinfo=SHANGHAI)  # Thursday
    dt = parse_relative_time("明天下午2点", now=now)
    assert dt is not None
    assert dt.year == 2026 and dt.month == 7 and dt.day == 10
    assert dt.hour == 14
    assert dt.tzinfo == SHANGHAI


def test_next_monday_from_thursday():
    # Spec example: 2026-07-09 (Thu) → 下周一 = 2026-07-13 14:00
    now = datetime(2026, 7, 9, 12, 0, tzinfo=SHANGHAI)
    dt = parse_relative_time("下周一 14:00", now=now)
    assert dt is not None
    assert dt.date().isoformat() == "2026-07-13"
    assert dt.hour == 14


def test_absolute_chinese_date():
    now = datetime(2026, 7, 9, 8, 0, tzinfo=SHANGHAI)
    dt = parse_relative_time("7月10号下午2点面试", now=now)
    assert dt is not None
    assert dt.month == 7 and dt.day == 10 and dt.hour == 14


def test_today():
    now = datetime(2026, 7, 9, 9, 0, tzinfo=SHANGHAI)
    dt = parse_relative_time("今天 10:30", now=now)
    assert dt is not None
    assert dt.day == 9 and dt.hour == 10 and dt.minute == 30


def test_format_shanghai():
    dt = datetime(2026, 7, 10, 14, 0, tzinfo=SHANGHAI)
    assert format_shanghai(dt) == "7月10日 14:00"


def test_unparseable_returns_none():
    assert parse_relative_time("随便聊聊") is None
    assert parse_relative_time("") is None
