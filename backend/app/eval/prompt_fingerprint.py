"""Stable prompt fingerprint helpers (T039, US9).

A prompt fingerprint is a stable, deterministic identifier for a (prompt +
tool definitions + message history) triple. It is the join field that lets
PM metrics, eval results, and badcase evidence roll up by prompt identity
across runs.

Why fingerprint instead of just ``prompt_version``:

- ``prompt_version`` is a human-managed string (``"v1.2.3"``) that changes
  only on human-intended releases. Fingerprint is derived from the actual
  prompt text so that **any** prompt change — even a typo in a comment —
  produces a new fingerprint. This is what eval regression tracking needs.
- The fingerprint is short (16 hex chars) so it's readable in logs and
  can be indexed as a regular varchar.

Determinism contract:

- Same input → same hash. Always. No timestamps, no random salts.
- ``tool_defs`` is alphabetized (sorted by tool name) so the order in
  which tools are passed does not change the fingerprint.
- ``messages`` is serialized in order, but for stability we strip
  volatile fields (timestamps, request ids) before hashing.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------


def _stable_json(obj: Any) -> str:
    """Serialize ``obj`` to a stable JSON string.

    - ``sort_keys=True`` — dict key order does not matter.
    - ``separators=(",", ":")`` — no whitespace, deterministic format.
    - ``ensure_ascii=False`` — preserves Chinese characters verbatim
      (matches the existing 032 prompt_caching convention).
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonicalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip volatile fields from a message list.

    Volatile fields we strip:

    - ``timestamp`` / ``created_at`` / ``ts`` — every LLM call has a
      fresh wall-clock time, but the prompt identity is about content.
    - ``request_id`` / ``id`` — request-scoped correlation id.
    - ``trace_id`` / ``run_id`` — different runs share the same prompt.

    Anything else (role, content, name, tool_call_id) is preserved.
    """
    volatile_keys = {
        "timestamp",
        "created_at",
        "ts",
        "request_id",
        "id",
        "trace_id",
        "run_id",
        "_ts",
    }
    out: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            out.append({"value": str(m)})
            continue
        clean = {k: v for k, v in m.items() if k not in volatile_keys}
        out.append(clean)
    return out


def _canonicalize_tool_defs(tool_defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alphabetize tool defs by ``name`` (or ``function.name``).

    The order in which tool definitions are registered varies by call
    site; the fingerprint must not change because the agent file was
    edited to swap a tool's order.
    """
    if not tool_defs:
        return []
    sorted_defs = sorted(
        tool_defs,
        key=lambda td: (
            (td.get("name") if isinstance(td, dict) else None)
            or (
                td.get("function", {}).get("name")
                if isinstance(td, dict) and isinstance(td.get("function"), dict)
                else None
            )
            or ""
        ),
    )
    return sorted_defs


def _short_hash(canonical: str, *, length: int = 16) -> str:
    """Return the first ``length`` hex chars of SHA256(canonical)."""
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:length]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_prompt_fingerprint(
    system_prompt: str,
    tool_defs: list[dict[str, Any]],
    messages: list[dict[str, Any]],
) -> str:
    """SHA256 stable hash of the canonical prompt representation.

    Args:
        system_prompt: The system prompt string. Required — pass empty
            string if the model call has no system prompt.
        tool_defs: List of tool/function definitions. Order-independent
            (alphabetized internally).
        messages: Chat-style message history. Volatile fields
            (timestamps, request ids) are stripped.

    Returns:
        16-character hex string. Identical inputs always produce the
        same output (no timestamps, no random salt).
    """
    canonical = _stable_json(
        {
            "system": system_prompt,
            "tools": _canonicalize_tool_defs(tool_defs or []),
            "messages": _canonicalize_messages(messages or []),
        }
    )
    return _short_hash(canonical)


def compute_version_fingerprint(
    version: str,
    model: str,
    rubric_version: str,
) -> str:
    """SHA256 stable hash for the (version, model, rubric_version) triple.

    Distinct from ``compute_prompt_fingerprint`` because:

    - The prompt fingerprint identifies the *content* of the prompt.
    - The version fingerprint identifies the *attribution triple*
      (version × model × rubric_version), which is what dashboard
      dimensions roll up against.

    Used by eval runner to stamp the version dimension of an EvalRun.
    """
    canonical = _stable_json(
        {
            "version": version,
            "model": model,
            "rubric_version": rubric_version,
        }
    )
    return _short_hash(canonical)


__all__ = [
    "compute_prompt_fingerprint",
    "compute_version_fingerprint",
]
