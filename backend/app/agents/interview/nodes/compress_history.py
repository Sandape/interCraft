"""REQ-042 US-2 FR-005 — interview compress_history node.

Triggers on **either** of two conditions:
* Active: ``len(messages) >= ACTIVE_TRIGGER_MESSAGE_COUNT`` (20)
* Passive: ``_estimate_tokens(messages) >= PASSIVE_TRIGGER_RATIO * window``

On trigger, the node:
1. Slices off the oldest ``len(messages) - retain`` messages.
2. Asks the LLM to summarize the dropped messages into a single
   system message.
3. Returns ``{"messages": [summary_system_msg] + retained,
              "compress_history_summary": CompressedHistory(...)}``

Per L041-003 (real E2E), the LLM call is **not** mocked here — the
graph.ainvoke E2E test in test_042_compress_history.py drives a real
DEEPSEEK call. Per L041-004 (4 surface sync), the node writes both
``messages`` AND ``compress_history_summary`` so downstream
``_question_gen_next_or_human`` router can observe the state delta.

Per L041-005 (RuntimeError inheritance), this node does not raise —
it captures LLM errors into ``state["warning"]`` per the
``@node_error_handler`` decorator's contract, so the graph
continues executing rather than aborting.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.interview.noop import noop_state_delta
from app.agents.utils.compress_history import (
    ACTIVE_TRIGGER_MESSAGE_COUNT,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_RETAIN_MESSAGES,
    PASSIVE_TRIGGER_RATIO,
    CompressedHistory,
    _estimate_tokens,
)
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node


@traced_node("interview.compress_history")
@node_error_handler(fallback_strategy="use_previous")
async def compress_history_node(state: Any) -> dict[str, Any]:
    """Compress message history when active or passive trigger fires.

    Active trigger: ``len(messages) >= 20``.
    Passive trigger: ``_estimate_tokens(messages) >= 0.8 * window``.

    Returns an empty dict (no-op) when neither trigger fires. Returns
    a state delta with the new messages list + CompressedHistory
    summary on success; returns ``{"warning": ...}`` on LLM failure
    (the original messages are kept untouched so the conversation
    can continue).
    """
    # Dual-form state read (per 040 + 041 dual-guard pattern).
    if isinstance(state, dict):
        messages = list(state.get("messages", []) or [])
    else:
        messages = list(getattr(state, "messages", []) or [])

    if not messages:
        return noop_state_delta(state)

    # Decide which trigger fired (active wins ties).
    active = len(messages) >= ACTIVE_TRIGGER_MESSAGE_COUNT
    tokens = _estimate_tokens(messages)
    passive = tokens >= int(PASSIVE_TRIGGER_RATIO * DEFAULT_CONTEXT_WINDOW_TOKENS)

    if not (active or passive):
        return noop_state_delta(state)

    triggered_by = "active" if active else "passive"
    retain = DEFAULT_RETAIN_MESSAGES
    to_summarize = messages[:-retain] if len(messages) > retain else messages[:-1]
    retained = messages[-retain:] if len(messages) > retain else messages[-1:]

    if isinstance(state, dict):
        user_id = str(state.get("user_id") or "unknown")
        thread_id = str(state.get("thread_id") or "unknown")
    else:
        user_id = str(getattr(state, "user_id", None) or "unknown")
        thread_id = str(getattr(state, "thread_id", None) or "unknown")

    # Try the LLM summary; on failure keep the originals and warn.
    try:
        summary_text = await _summarize_messages(
            to_summarize, user_id=user_id, thread_id=thread_id
        )
    except Exception as exc:  # noqa: BLE001 — boundary catch
        return {
            "warning": f"compress_history failed: {exc}",
        }

    summary_msg = {
        "role": "system",
        "content": f"[Compressed] {summary_text}",
    }
    new_messages = [summary_msg, *retained]

    summary = CompressedHistory(
        summary=summary_text,
        retained_message_count=len(retained),
        original_message_count=len(messages),
        compressed_at=datetime.now(tz=timezone.utc),
        triggered_by=triggered_by,  # type: ignore[arg-type]
    )

    return {
        "messages": new_messages,
        "compress_history_summary": summary,
    }


async def _summarize_messages(
    messages: list[Any],
    *,
    user_id: str = "unknown",
    thread_id: str = "unknown",
) -> str:
    """Call the LLM to summarize a list of messages (flash model).

    Implementation note: we lazily import the LLM client to keep this
    module importable in unit tests that don't have a DEEPSEEK key
    configured. The LLM client raises ``LLMInvokeError`` on failure
    which propagates to the ``@node_error_handler`` wrapper above.
    """
    from app.agents.llm_client import get_llm_client

    # Serialise messages to a plain text prompt.
    parts: list[str] = []
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role", "user")
            content = m.get("content", "")
        else:
            role = getattr(m, "role", "user") or "user"
            content = getattr(m, "content", "")
        parts.append(f"{role}: {content}")
    prompt = (
        "Summarize the following conversation in 1-3 sentences. "
        "Preserve any concrete facts (names, scores, decisions) "
        "the user mentioned.\n\n"
        + "\n".join(parts)
    )
    llm = get_llm_client()
    result = await llm.invoke(
        messages=[{"role": "user", "content": prompt}],
        estimated_tokens=1500,
        user_id=user_id,
        thread_id=thread_id,
        node_name="compress_history",
    )
    return str(result.get("content") or "").strip()


__all__ = ["compress_history_node"]
