"""REQ-041 US1 FR-003 — NodeError Pydantic + exception classifier.

AC-3.5: ``NodeError`` carries a 6-bucket ``category`` Literal whose string
values match REQ-038's ``parse_structured_output`` subclass
``__name__.lower()`` exactly:

- ``schema_invalid`` ↔ ``SchemaInvalid`` (038)
- ``parse_fail``     ↔ ``ParseFail`` (038)
- ``quota``          ↔ ``Quota`` (038)
- ``timeout``        ↔ ``Timeout`` (038)
- ``oob``            ↔ ``OutOfBounds`` (038)
- ``checkpointer_unavailable`` ↔ ``CheckpointerUnavailableError`` (023)

AC-3.6 / AC-3.6a: ``classify_exception`` MUST import those subclasses
(rather than re-implementing a parallel taxonomy). This keeps error
classification routable from any caller: the graph node, the API
serialiser, or the front-end error mapper.

Design contract:
- ``NodeError`` is plain ``BaseModel`` (no Pydantic v2 strict mode here;
  legacy ``error: str`` is preserved on ``InterviewGraphState`` for the
  1-week dual-track window per AC-3.1a).
- ``timestamp`` is ISO 8601 UTC string (callers can format however they
  like; we default to ``None`` so the producer can opt-in).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel

# 038 subclasses — exception taxonomy is owned by REQ-038, we reuse it.
from app.agents.structured_output.errors import (
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    Timeout,
)

# 023 — graph checkpointer error
from app.agents.checkpointer import CheckpointerUnavailableError


# ---------------------------------------------------------------------------
# 6-bucket Literal — must match 038 subclass __name__.lower() literally
# ---------------------------------------------------------------------------
NodeErrorCategory = Literal[
    "schema_invalid",
    "parse_fail",
    "quota",
    "timeout",
    "oob",
    "checkpointer_unavailable",
    # REQ-042 US-1 FR-004 — two new categories.
    # - "graph_recursion": LangGraph ``recursion_limit`` exceeded.
    # - "loop_terminated": per-agent ``Configuration.max_iterations`` soft
    #   cap exceeded; raised by ``iteration_guard_node``.
    "graph_recursion",
    "loop_terminated",
]


class NodeError(BaseModel):
    """Failure envelope attached to ``state["error"]`` on hard fallback.

    Populated by ``@node_error_handler`` when ``fallback_strategy ==
    "use_previous"``. The same shape is mirrored to the API response as
    ``error_category`` + ``node_name`` + ``cause`` fields (per AC-3.4).
    """

    category: NodeErrorCategory
    node_name: str
    cause: str
    retry_after: Optional[int] = None
    timestamp: Optional[str] = None

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        node_name: str,
        retry_after: Optional[int] = None,
    ) -> "NodeError":
        """Build a ``NodeError`` from any exception, classifying it.

        Per AC-3.6, ``classify_exception`` does isinstance checks against
        the actual REQ-038 / REQ-023 exception classes — no parallel
        taxonomy.
        """
        category = classify_exception(exc)
        # `timestamp` ISO 8601 UTC (e.g. "2026-07-03T14:25:00.000+00:00")
        ts = datetime.now(tz=timezone.utc).isoformat()
        return cls(
            category=category,
            node_name=node_name,
            cause=str(exc),
            retry_after=retry_after,
            timestamp=ts,
        )


# ---------------------------------------------------------------------------
# Exception classifier (AC-3.6)
# ---------------------------------------------------------------------------
def classify_exception(exc: BaseException) -> NodeErrorCategory:
    """Map a Python exception to one of the 6 ``NodeError`` categories.

    Order: most specific (subclass) first. Defaults to ``"schema_invalid"``
    because the dominant failure mode for LLM nodes is malformed structured
    output — clients can treat unknown exception types as "not LLM-quota
    or timeout, so probably a payload problem".
    """
    if isinstance(exc, CheckpointerUnavailableError):
        return "checkpointer_unavailable"
    if isinstance(exc, Quota):
        return "quota"
    if isinstance(exc, Timeout):
        return "timeout"
    if isinstance(exc, OutOfBounds):
        return "oob"
    if isinstance(exc, ParseFail):
        return "parse_fail"
    if isinstance(exc, SchemaInvalid):
        return "schema_invalid"
    # duck-typed fallbacks for environments where the 038 SDK is absent
    name = type(exc).__name__.lower()
    if name == "checkpointerunavailableerror":
        return "checkpointer_unavailable"
    if name == "quota":
        return "quota"
    if name == "timeout":
        return "timeout"
    if name == "outofbounds":
        return "oob"
    if name == "parsefail":
        return "parse_fail"
    if name == "schemainvalid":
        return "schema_invalid"
    # REQ-042 US-1 FR-004 — duck-typed for the new categories.
    if name == "graphrecursionerror":
        return "graph_recursion"
    if name == "maxiterationsreached":
        return "loop_terminated"
    return "schema_invalid"


def serialize_state_error(
    state_error: "Any | None" = None,
    state_error_legacy: "str | None" = None,
) -> "dict[str, Any]":
    """Project ``state["error"]`` + ``state["error_legacy"]`` to API JSON.

    Per AC-3.4 / AC-3.1a / AC-3.7a — the API response MUST expose:

    - ``error_legacy_str`` — the str-typed legacy field (during the 1-week
      dual-track window). Once the release manager deletes the legacy
      str field, this key will go away too.
    - ``error_category`` — the 6-bucket category from ``NodeError``.
    - ``node_name`` — the node that failed.
    - ``cause`` — the exception's str() representation (best-effort).
    - ``retry_after`` and ``timestamp`` — optional fields.

    Untyped / no-error states yield only the keys they have populated.
    """
    from typing import Any as _Any  # local import to avoid recursion

    out: dict[str, _Any] = {}

    # AC-3.1a: legacy str is always reflected when present.
    if state_error_legacy is not None:
        out["error_legacy_str"] = state_error_legacy

    # AC-3.4 / AC-3.7a: typed envelope reflected via 4 keys.
    if state_error is not None:
        if isinstance(state_error, NodeError):
            payload = state_error.model_dump()
        elif isinstance(state_error, dict):
            payload = state_error
        else:
            payload = {}

        if "category" in payload:
            out["error_category"] = payload["category"]
        if "node_name" in payload:
            out["node_name"] = payload["node_name"]
        if "cause" in payload:
            out["cause"] = payload["cause"]
        if "retry_after" in payload and payload["retry_after"] is not None:
            out["retry_after"] = payload["retry_after"]
        if "timestamp" in payload and payload["timestamp"] is not None:
            out["timestamp"] = payload["timestamp"]

    return out


__all__ = ["NodeError", "NodeErrorCategory", "classify_exception", "serialize_state_error"]
