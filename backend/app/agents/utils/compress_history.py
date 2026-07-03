"""REQ-042 US-2 FR-005 + FR-006 — CompressedHistory Pydantic + token estimation.

``CompressedHistory`` is the structured payload written to
``state["compress_history_summary"]`` when the interview graph's
``compress_history_node`` triggers.

The token estimator is a heuristic (chars/4). It is intentionally
simple — we use it to *decide* whether to compress, not to *measure*
compression quality. Quality is verified downstream by AC-6.2 (real
E2E token drop >= 50% after compression).

The LLM call lives in ``compress_history_node`` (see
``app.agents.interview.nodes.compress_history``) so this module
stays LLM-client-free and importable from any context (e.g. tests
without the DEEPSEEK_API_KEY env var set).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# CompressedHistory — FR-006 Pydantic
# ---------------------------------------------------------------------------

TriggeredBy = Literal["active", "passive"]


class CompressedHistory(BaseModel):
    """Snapshot of a single compress_history pass.

    Attributes:
        summary: human-readable summary of the dropped messages.
        retained_message_count: how many recent messages were kept.
        original_message_count: how many messages were in state before
            compression.
        compressed_at: UTC timestamp when compression ran.
        triggered_by: ``"active"`` (len(messages) >= 20) or
            ``"passive"`` (token estimate >= 0.8 * context_window).
    """

    summary: str
    retained_message_count: int
    original_message_count: int
    compressed_at: datetime
    triggered_by: TriggeredBy


# ---------------------------------------------------------------------------
# Token estimation — heuristic (chars / 4 ≈ tokens for English/Chinese)
# ---------------------------------------------------------------------------

#: Default retain count (most recent N messages kept after compression).
DEFAULT_RETAIN_MESSAGES = 8

#: Default context window size in tokens (DeepSeek V4 Pro safe budget).
DEFAULT_CONTEXT_WINDOW_TOKENS = 16_000

#: Passive trigger threshold: fire when estimated tokens exceed this
#: fraction of the context window.
PASSIVE_TRIGGER_RATIO = 0.8

#: Active trigger threshold: fire when message count reaches this value.
ACTIVE_TRIGGER_MESSAGE_COUNT = 20


def _estimate_tokens(messages: list[Any]) -> int:
    """Crude token estimator: ~4 chars per token.

    Accepts a list of message dicts (LangGraph ``add_messages`` shape)
    or any object with a ``.content`` attribute. Returns 0 for empty
    input. Used to gate the *passive* trigger of compress_history.
    """
    if not messages:
        return 0
    total_chars = 0
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content", "")
        else:
            content = getattr(m, "content", "")
        if isinstance(content, str):
            total_chars += len(content)
        else:
            # list of content blocks (e.g. multimodal) — stringify
            total_chars += len(str(content))
    # Round up so a single non-empty message is >= 1 token.
    return max(1, total_chars // 4)


__all__ = [
    "ACTIVE_TRIGGER_MESSAGE_COUNT",
    "CompressedHistory",
    "DEFAULT_CONTEXT_WINDOW_TOKENS",
    "DEFAULT_RETAIN_MESSAGES",
    "PASSIVE_TRIGGER_RATIO",
    "TriggeredBy",
    "_estimate_tokens",
]
