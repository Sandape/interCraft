"""Unit tests for confirmations word lists."""

from app.modules.agent.conversation.confirmations import (
    CANCEL_WORDS,
    CONFIRM_WORDS,
    is_cancel,
    is_confirm,
)


def test_confirm_words():
    assert is_confirm("确认")
    assert is_confirm(" 好的 ")
    assert is_confirm("OK")
    assert is_confirm("是")
    assert not is_confirm("确认一下吧")  # exact match only
    assert not is_confirm("取消")


def test_cancel_words():
    assert is_cancel("取消")
    assert is_cancel("算了")
    assert is_cancel("no")
    assert not is_cancel("确认")
    assert not is_cancel("不要了吗")  # exact


def test_sets_non_empty():
    assert len(CONFIRM_WORDS) >= 5
    assert len(CANCEL_WORDS) >= 3
