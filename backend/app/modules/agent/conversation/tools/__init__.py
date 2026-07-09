"""Tool result helpers (REQ-054)."""

from __future__ import annotations

from typing import Any, TypedDict


class ToolResult(TypedDict, total=False):
    ok: bool
    reply_text: str
    data: dict[str, Any] | None
    error_code: str | None


def ok(reply_text: str, data: dict[str, Any] | None = None) -> ToolResult:
    return {"ok": True, "reply_text": reply_text, "data": data, "error_code": None}


def fail(
    reply_text: str,
    error_code: str,
    data: dict[str, Any] | None = None,
) -> ToolResult:
    return {
        "ok": False,
        "reply_text": reply_text,
        "data": data,
        "error_code": error_code,
    }


def pending(
    reply_text: str,
    action_type: str,
    params: dict[str, Any],
) -> ToolResult:
    """Prepare-phase success that needs confirmation (not yet executed)."""
    return {
        "ok": True,
        "reply_text": reply_text,
        "data": {
            "needs_confirmation": True,
            "pending_action": {"type": action_type, "params": params},
        },
        "error_code": None,
    }


def clarify(reply_text: str, data: dict[str, Any] | None = None) -> ToolResult:
    return {
        "ok": False,
        "reply_text": reply_text,
        "data": data,
        "error_code": "clarify",
    }
