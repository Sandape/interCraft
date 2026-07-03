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
    return "schema_invalid"


__all__ = ["NodeError", "NodeErrorCategory", "classify_exception"]
