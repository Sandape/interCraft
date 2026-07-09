"""Relative time parsing fixed to Asia/Shanghai (REQ-054 FR-006b)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

_WEEKDAY_CN = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


def now_shanghai(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI)
    if now.tzinfo is None:
        return now.replace(tzinfo=SHANGHAI)
    return now.astimezone(SHANGHAI)


def format_shanghai(dt: datetime) -> str:
    """Display absolute local time for confirmation cards."""
    local = now_shanghai(dt)
    return f"{local.month}月{local.day}日 {local.hour:02d}:{local.minute:02d}"


def _parse_clock(text: str) -> tuple[int, int] | None:
    """Extract HH:MM from common Chinese / numeric forms."""
    m = re.search(
        r"(上午|下午|晚上|中午)?\s*(\d{1,2})\s*[点:：]\s*(\d{1,2})?",
        text,
    )
    if not m:
        m2 = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
        if not m2:
            return None
        hour, minute = int(m2.group(1)), int(m2.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
        return None

    period, hour_s, minute_s = m.group(1), m.group(2), m.group(3)
    hour = int(hour_s)
    minute = int(minute_s) if minute_s else 0
    if period in ("下午", "晚上") and hour < 12:
        hour += 12
    if period == "中午" and hour < 12:
        hour = 12 if hour == 0 else hour
    if period == "上午" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _next_weekday(base: datetime, target_weekday: int, *, next_week: bool) -> datetime:
    """Return date at midnight Shanghai for target weekday.

    「下周一」= next week's Monday (always at least 1 day ahead, and if
    today is Monday and next_week, jump 7 days).
    「周一」without 下 = upcoming weekday (today if same day and clock later
    handled by caller).
    """
    current = base.weekday()  # Mon=0
    days_ahead = (target_weekday - current) % 7
    if next_week:
        if days_ahead == 0:
            days_ahead = 7
        else:
            # 「下周一」when today is Thursday → next Monday = days_ahead
            # Spec example: Thu 2026-07-09 → 下周一 = 2026-07-13 (4 days)
            # which is the upcoming Monday; Chinese「下周一」often means that.
            # Keep days_ahead as-is for upcoming Monday in the next calendar week
            # only when days_ahead would land this week AND we want next week.
            # Clarification: 下周一 from Thursday = Monday Jul 13 = +4 days.
            pass
    else:
        if days_ahead == 0:
            days_ahead = 0  # today
    return (base + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def parse_relative_time(
    raw: str,
    *,
    now: datetime | None = None,
    default_hour: int = 10,
    default_minute: int = 0,
) -> datetime | None:
    """Parse Chinese relative / absolute date-time to aware Asia/Shanghai datetime.

    Returns None if nothing recognizable.
    """
    if not raw or not str(raw).strip():
        return None

    text = str(raw).strip()
    base = now_shanghai(now)
    clock = _parse_clock(text)
    hour = clock[0] if clock else default_hour
    minute = clock[1] if clock else default_minute

    # Absolute: 7月10号 / 7月10日 / 2026-07-10 / 2026年7月10日
    m_abs = re.search(
        r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?",
        text,
    )
    if m_abs:
        year = int(m_abs.group(1)) if m_abs.group(1) else base.year
        month, day = int(m_abs.group(2)), int(m_abs.group(3))
        try:
            return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI)
        except ValueError:
            return None

    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m_iso:
        year, month, day = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI)
        except ValueError:
            return None

    # Relative day keywords
    day_offset: int | None = None
    if "大后天" in text:
        day_offset = 3
    elif "后天" in text:
        day_offset = 2
    elif "明天" in text:
        day_offset = 1
    elif "今天" in text or "今日" in text:
        day_offset = 0

    if day_offset is not None:
        target = base + timedelta(days=day_offset)
        return target.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Weekday: 下周一 / 本周三 / 周一
    m_wd = re.search(r"(下)?(?:周|星期)([一二三四五六日天])", text)
    if m_wd:
        next_week = bool(m_wd.group(1))
        wd = _WEEKDAY_CN[m_wd.group(2)]
        target_day = _next_weekday(base, wd, next_week=next_week)
        return target_day.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Clock only → today (or tomorrow if already past)
    if clock:
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate < base:
            candidate = candidate + timedelta(days=1)
        return candidate

    return None


__all__ = [
    "SHANGHAI",
    "now_shanghai",
    "format_shanghai",
    "parse_relative_time",
]
