"""Helpers for LangGraph node updates that must be non-empty.

LangGraph 0.2.x rejects ``return {}`` from a node with:
``Must write to at least one of [...]``. No-op / early-exit nodes therefore
need to echo a stable identity field so the graph can continue.
"""
from __future__ import annotations

from typing import Any


def noop_state_delta(state: Any) -> dict[str, Any]:
    """Return a minimal non-empty state delta that does not change semantics.

    Preference order: ``thread_id`` → ``user_id`` → ``current_question``.
    """
    if isinstance(state, dict):
        if state.get("thread_id"):
            return {"thread_id": state["thread_id"]}
        if state.get("user_id"):
            return {"user_id": state["user_id"]}
        return {"current_question": int(state.get("current_question") or 0)}

    tid = getattr(state, "thread_id", None)
    if tid:
        return {"thread_id": tid}
    uid = getattr(state, "user_id", None)
    if uid:
        return {"user_id": uid}
    return {"current_question": int(getattr(state, "current_question", 0) or 0)}
