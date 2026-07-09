"""REQ-033 US7 (T126) — TraceRunRef helpers.

Pure helpers for building a :class:`TraceRunRef` from an
``AIInvocationRecord`` row (the canonical "the LLM call that produced
this result" join).

The TraceRunRef dataclass is the eval / badcase / PM-dashboard
contract for "where did this case come from?":

- ``case_id`` — eval case id (``str | None``).
- ``trace_id`` — OTel trace id hex (``str | None``). The OTel SDK
  populates this when a span was active during the LLM call;
  ``None`` when no span was active (use the literal
  ``"unavailable"`` in renderers).
- ``run_id`` — eval run UUID (``str | None``). Set by the
  LLM client hook on every invocation when an eval run is in flight.
- ``langsmith_url`` — LangSmith deep link (``str | None``). Per
  US6 deferral, this is always ``None`` — the LangSmith SDK is not
  installed.

The module is pure-Python (no DB / no async / no I/O) so it is
trivially unit-testable in isolation. All public symbols are
re-exported via ``app.modules.telemetry_contracts.__init__``.

US7 contract (T126): callers MUST treat ``None`` as "unavailable" and
render the literal string ``"unavailable"`` in UI / markdown / JSON
output. The dataclass uses ``Optional`` so callers can distinguish
"field is missing" from "field is the empty string".
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.telemetry_contracts.models import AIInvocationRecord


@dataclass(frozen=True)
class TraceRunRef:
    """Reference tuple identifying an eval case's originating trace + run.

    All four fields are ``Optional`` to make "missing" explicit. Renderers
    MUST map ``None`` to the literal string ``"unavailable"`` (not silent
    omission, not empty string).

    Attributes
    ----------
    case_id:
        Eval case id (always set when constructed from a CaseResult).
    trace_id:
        OTel trace id (32-char lowercase hex). ``None`` when no span
        was active during the originating LLM call. Renderers MUST
        show ``"unavailable"``.
    run_id:
        Eval run UUID (string form). ``None`` when the case was
        not part of an eval run. Renderers MUST show ``"unknown"``
        or ``"unavailable"``.
    langsmith_url:
        LangSmith deep link to the experiment / run. ``None`` when
        LangSmith is not enabled (US6 deferred per user decision).
        Renderers MUST show ``"unavailable"``.
    """

    case_id: str | None
    trace_id: str | None
    run_id: str | None
    langsmith_url: str | None


def extract_trace_id_from_ai_invocation(
    record: Any,
) -> str | None:
    """Return the trace_id stored on an ``AIInvocationRecord`` row.

    The ``ai_invocation_records`` table stores trace_id as a
    nullable string column. Returns ``None`` when the column is
    ``None`` / empty string (defensive — ``None`` from the DB
    becomes ``None`` here, not ``""``).

    Accepts an ORM object, a dict, or any object with a
    ``trace_id`` attribute. This keeps the helper usable both in
    live query code (ORM) and in tests (dict / mock).
    """
    if record is None:
        return None
    # Dict path.
    if isinstance(record, dict):
        val = record.get("trace_id")
        if val is None or val == "":
            return None
        return str(val)
    # ORM / attribute path.
    val = getattr(record, "trace_id", None)
    if val is None or val == "":
        return None
    return str(val)


def lookup_run_metadata(
    record: Any,
) -> str | None:
    """Return the run_id stored on an ``AIInvocationRecord`` row.

    The LLM client hook (US9 T040) populates ``run_id`` (UUID) on
    every invocation when an eval run is in flight; otherwise it's
    ``None``. Returns the string form so the TraceRunRef dataclass
    stays primitive-only (no UUID import needed downstream).
    """
    if record is None:
        return None
    if isinstance(record, dict):
        val = record.get("run_id")
    else:
        val = getattr(record, "run_id", None)
    if val is None:
        return None
    return str(val)


def build_trace_run_ref(
    case_id: str | None,
    record: Any,
    *,
    langsmith_url: str | None = None,
) -> TraceRunRef:
    """Build a :class:`TraceRunRef` from an ``AIInvocationRecord`` row.

    Convenience constructor — combines ``extract_trace_id_from_ai_invocation``
    + ``lookup_run_metadata`` + the explicit ``case_id`` argument.

    Parameters
    ----------
    case_id:
        The eval case id (``str``). May be ``None`` for orphan
        records (no eval case).
    record:
        An ``AIInvocationRecord`` ORM row, a dict, or any object
        with ``trace_id`` / ``run_id`` attributes. ``None`` is
        accepted (all fields become ``None``).
    langsmith_url:
        Optional explicit LangSmith URL. Defaults to ``None`` since
        US6 is deferred and LangSmith SDK is not installed.
    """
    trace_id = extract_trace_id_from_ai_invocation(record)
    run_id = lookup_run_metadata(record)
    return TraceRunRef(
        case_id=case_id,
        trace_id=trace_id,
        run_id=run_id,
        langsmith_url=langsmith_url,
    )


async def _existing_eval_run_id(session: AsyncSession, run_id: UUID | None) -> UUID | None:
    if run_id is None:
        return None
    try:
        exists = await session.scalar(
            text("SELECT run_id FROM eval_runs WHERE run_id = :run_id LIMIT 1"),
            {"run_id": run_id},
        )
        return run_id if exists is not None else None
    except Exception:
        return None


async def insert_ai_invocation(
    session: AsyncSession,
    *,
    user_id: UUID,
    invocation_id: UUID,
    graph: str,
    node: str,
    model: str,
    prompt_fingerprint: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost: Decimal | None,
    latency_ms: int | None,
    retry_count: int,
    status: str,
    error_category: str | None,
    run_id: UUID | None = None,
    trace_id: str | None = None,
) -> AIInvocationRecord:
    """Persist one AI invocation summary row.

    ``run_id`` is an eval-run FK. Normal interview thread ids are not eval
    runs, so they are stored as ``NULL`` while trace/node/cost visibility
    remains intact.
    """

    record = AIInvocationRecord(
        id=uuid4(),
        invocation_id=invocation_id,
        user_id=user_id,
        run_id=await _existing_eval_run_id(session, run_id),
        trace_id=trace_id,
        graph=graph or "unknown",
        node=node or "unknown",
        model=model or "unknown",
        prompt_fingerprint=prompt_fingerprint or "unknown",
        prompt_tokens=max(0, int(prompt_tokens)),
        completion_tokens=max(0, int(completion_tokens)),
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        retry_count=max(0, int(retry_count)),
        status=status,
        error_category=error_category,
    )
    session.add(record)
    await session.flush()
    return record


# ---------------------------------------------------------------------------
# Display helpers — map ``None`` to the canonical "unavailable" marker
# ---------------------------------------------------------------------------


#: Literal marker used in renderers when a TraceRunRef field is missing.
TRACE_UNAVAILABLE: str = "unavailable"


def trace_id_for_display(ref: TraceRunRef) -> str:
    """Return the trace id for UI rendering.

    Maps ``None`` to ``"unavailable"`` per US7 T123 contract — the
    report must show an explicit marker, never silent omission.
    """
    if ref.trace_id is None or ref.trace_id == "":
        return TRACE_UNAVAILABLE
    return ref.trace_id


def run_id_for_display(ref: TraceRunRef) -> str:
    """Return the run id for UI rendering.

    Maps ``None`` to ``"unknown"`` (consistent with the existing
    EvalReport / CaseResultModel default). ``""`` is also mapped
    to ``"unknown"`` defensively.
    """
    if ref.run_id is None or ref.run_id == "":
        return "unknown"
    return ref.run_id


def langsmith_url_for_display(ref: TraceRunRef) -> str:
    """Return the LangSmith URL for UI rendering.

    Per US6 deferral, this is always ``"unavailable"`` when the
    SDK is not installed. The function still consults the ref so
    a future US can flip the marker without changing callers.
    """
    if ref.langsmith_url is None or ref.langsmith_url == "":
        return TRACE_UNAVAILABLE
    return ref.langsmith_url


__all__ = [
    "TRACE_UNAVAILABLE",
    "TraceRunRef",
    "build_trace_run_ref",
    "extract_trace_id_from_ai_invocation",
    "insert_ai_invocation",
    "langsmith_url_for_display",
    "lookup_run_metadata",
    "run_id_for_display",
    "trace_id_for_display",
]
