"""Confirmation / cancel word lists for WeChat write-ops (REQ-054)."""

from __future__ import annotations

CONFIRM_WORDS: frozenset[str] = frozenset(
    {
        "确认",
        "是",
        "好的",
        "好",
        "可以",
        "行",
        "ok",
        "OK",
        "Ok",
        "yes",
        "Yes",
        "YES",
        "确定",
        "同意",
        "没问题",
        "嗯",
        "对",
    }
)

CANCEL_WORDS: frozenset[str] = frozenset(
    {
        "取消",
        "不要",
        "算了",
        "不了",
        "否",
        "no",
        "No",
        "NO",
        "放弃",
        "别了",
        "不用了",
    }
)


def _normalize(text: str) -> str:
    return (text or "").strip()


def is_confirm(text: str) -> bool:
    """Return True if the message is a confirmation word (exact match after strip)."""
    return _normalize(text) in CONFIRM_WORDS


def is_cancel(text: str) -> bool:
    """Return True if the message is a cancel word (exact match after strip)."""
    return _normalize(text) in CANCEL_WORDS


__all__ = [
    "CONFIRM_WORDS",
    "CANCEL_WORDS",
    "is_confirm",
    "is_cancel",
]
