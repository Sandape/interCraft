"""WS event serialization helpers (T014).

Generates JSON event payloads per contracts/ws-events.md.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any


def _new_event_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def make_event(
    event_type: str,
    session_id: str,
    node_name: str,
    payload: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Build a WS event message.

    Args:
        event_type: e.g. "node.started", "token.delta", "node.completed", "error"
        session_id: interview session UUID
        node_name: intake / question_gen / score / report / system
        payload: event-specific data
        event_id: optional override (auto-generated uuid if not provided)
    """
    return {
        "type": event_type,
        "event_id": event_id or _new_event_id(),
        "session_id": session_id,
        "timestamp": _now_iso(),
        "node_name": node_name,
        "payload": payload or {},
    }


def serialize_event(event: dict[str, Any]) -> str:
    """Serialize an event dict to a single-line JSON string."""
    return json.dumps(event, ensure_ascii=False) + "\n"


def make_token_delta(
    session_id: str,
    node_name: str,
    content: str,
    index: int,
) -> dict[str, Any]:
    """Shortcut for token.delta events."""
    return make_event(
        "token.delta",
        session_id,
        node_name,
        payload={"content": content, "index": index},
    )


def make_node_started(
    session_id: str,
    node_name: str,
    current_question: int | None = None,
    total_questions: int = 5,
) -> dict[str, Any]:
    """Shortcut for node.started events."""
    payload: dict[str, Any] = {"total_questions": total_questions}
    if current_question is not None:
        payload["current_question"] = current_question
    return make_event("node.started", session_id, node_name, payload=payload)


def make_node_completed(
    session_id: str,
    node_name: str,
    checkpoint_id: str,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shortcut for node.completed events."""
    payload: dict[str, Any] = {"checkpoint_id": checkpoint_id}
    if summary:
        payload["summary"] = summary
    return make_event("node.completed", session_id, node_name, payload=payload)


def make_error_event(
    session_id: str,
    node_name: str,
    code: str,
    message: str,
    retryable: bool = False,
    retry_count: int = 0,
) -> dict[str, Any]:
    """Shortcut for error events."""
    return make_event(
        "error",
        session_id,
        node_name,
        payload={
            "code": code,
            "message": message,
            "retryable": retryable,
            "retry_count": retry_count,
        },
    )


def make_agent_interrupt(
    thread_id: str,
    graph: str,
    node: str,
    *,
    proposed_patches: list | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Shortcut for agent interrupt events (Phase 5 M16)."""
    payload: dict[str, Any] = {}
    if proposed_patches is not None:
        payload["proposed_patches"] = proposed_patches
    if summary is not None:
        payload["summary"] = summary
    return {
        "event": "interrupt",
        "thread_id": thread_id,
        "graph": graph,
        "node": node,
        "data": payload,
    }


def make_agent_final(
    thread_id: str,
    graph: str,
    *,
    summary: str | None = None,
    dimensions_updated: bool = False,
) -> dict[str, Any]:
    """Shortcut for agent.final events (Phase 5 M18)."""
    return {
        "event": "agent.final",
        "graph": graph,
        "thread_id": thread_id,
        "data": {
            "summary": summary or "",
            "dimensions_updated": dimensions_updated,
        },
    }


__all__ = [
    "make_agent_final",
    "make_agent_interrupt",
    "make_error_event",
    "make_event",
    "make_node_completed",
    "make_node_started",
    "make_token_delta",
    "serialize_event",
]
