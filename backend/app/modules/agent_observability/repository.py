from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select

from app.modules.agent_observability.models import (
    EvalCaseResult,
    EvalRun,
    LLMCallRecord,
    ObservabilityCoverageGap,
    ObservabilityPayload,
    ObservabilitySpan,
    ObservabilityTrace,
    ToolOperationRecord,
)


REQ045_TRACE_SURFACES: tuple[dict[str, str], ...] = (
    {
        "surface": "fastapi_http",
        "feature_area": "api",
        "entrypoint": "TraceIDMiddleware",
        "evidence": "HTTP requests bind and echo X-Trace-Id/X-Run-Id.",
    },
    {
        "surface": "interview_websocket",
        "feature_area": "interview",
        "entrypoint": "interview websocket messages",
        "evidence": "WS submit/reconnect messages bind run and trace context.",
    },
    {
        "surface": "arq_worker",
        "feature_area": "worker",
        "entrypoint": "ARQ enqueue/job hooks",
        "evidence": "ARQ enqueue metadata carries W3C traceparent and run id.",
    },
    {
        "surface": "langgraph_nodes",
        "feature_area": "agent",
        "entrypoint": "@traced_node decorators",
        "evidence": "LangGraph node spans remain the canonical graph-level trail.",
    },
    {
        "surface": "llm_invocations",
        "feature_area": "llm",
        "entrypoint": "LLMClient/MockLLMClient",
        "evidence": "LLM child spans include model, token, run, and trace attributes.",
    },
)


class WriteSession(Protocol):
    def add(self, item: object) -> None: ...

    async def flush(self) -> None: ...


async def create_trace(
    session: WriteSession,
    *,
    trace_id: str,
    user_id: UUID,
    business_event_id: str | None,
    environment: str,
    feature_area: str,
    agent_name: str,
    status: str,
    started_at: datetime,
    ended_at: datetime | None = None,
    retention_expires_at: datetime | None = None,
    version_context: dict[str, Any] | None = None,
) -> ObservabilityTrace:
    row = ObservabilityTrace(
        trace_id=trace_id,
        user_id=user_id,
        business_event_id=business_event_id,
        environment=environment,
        feature_area=feature_area,
        agent_name=agent_name,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        retention_expires_at=retention_expires_at,
        version_context=version_context or {},
    )
    session.add(row)
    await session.flush()
    return row


async def get_trace(session, *, trace_id: str) -> ObservabilityTrace | None:
    result = await session.execute(
        select(ObservabilityTrace).where(ObservabilityTrace.trace_id == trace_id)
    )
    return result.scalar_one_or_none()


async def list_traces(
    session,
    *,
    user_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[ObservabilityTrace]:
    stmt = select(ObservabilityTrace)
    if user_id is not None:
        stmt = stmt.where(ObservabilityTrace.user_id == user_id)
    if status is not None:
        stmt = stmt.where(ObservabilityTrace.status == status)
    stmt = stmt.order_by(ObservabilityTrace.started_at.desc()).limit(max(1, min(limit, 200)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_span(
    session: WriteSession,
    *,
    span_id: str,
    trace_id: str,
    user_id: UUID,
    parent_span_id: str | None,
    node_name: str,
    status: str,
    started_at: datetime,
    agent_run_id: str | None = None,
    span_kind: str = "node",
    ended_at: datetime | None = None,
    input_payload_id: str | None = None,
    output_payload_id: str | None = None,
    error_summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ObservabilitySpan:
    row = ObservabilitySpan(
        span_id=span_id,
        trace_id=trace_id,
        user_id=user_id,
        parent_span_id=parent_span_id,
        agent_run_id=agent_run_id,
        node_name=node_name,
        span_kind=span_kind,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        input_payload_id=input_payload_id,
        output_payload_id=output_payload_id,
        error_summary=error_summary,
        metadata_json=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def list_spans_for_trace(session, *, trace_id: str) -> list[ObservabilitySpan]:
    result = await session.execute(
        select(ObservabilitySpan)
        .where(ObservabilitySpan.trace_id == trace_id)
        .order_by(ObservabilitySpan.started_at.asc())
    )
    return list(result.scalars().all())


async def list_llm_calls_for_trace(session, *, trace_id: str) -> list[LLMCallRecord]:
    result = await session.execute(
        select(LLMCallRecord)
        .where(LLMCallRecord.trace_id == trace_id)
        .order_by(LLMCallRecord.started_at.asc())
    )
    return list(result.scalars().all())


async def list_tool_operations_for_span(
    session,
    *,
    span_id: str,
) -> list[ToolOperationRecord]:
    result = await session.execute(
        select(ToolOperationRecord)
        .where(ToolOperationRecord.span_id == span_id)
        .order_by(ToolOperationRecord.started_at.asc())
    )
    return list(result.scalars().all())


async def get_eval_case_for_trace(session, *, trace_id: str) -> EvalCaseResult | None:
    result = await session.execute(
        select(EvalCaseResult).where(EvalCaseResult.trace_id == trace_id)
    )
    return result.scalar_one_or_none()


def _row_duration_ms(trace: ObservabilityTrace) -> int:
    if trace.ended_at is None:
        return 0
    return max(0, int((trace.ended_at - trace.started_at).total_seconds() * 1000))


def _row_eval_status(eval_case: EvalCaseResult | None) -> str:
    if eval_case is None:
        return "not_run"
    return "failed" if str(eval_case.verdict).lower() in {"fail", "failed"} else "passed"


def _row_next_node(
    *,
    trace: ObservabilityTrace,
    spans: list[ObservabilitySpan],
) -> str:
    if trace.status == "success":
        return "complete"
    for span in spans:
        if span.span_kind == "node" and span.status == "error":
            return span.node_name
    return "unknown"


def _trace_search_haystack(
    *,
    trace: ObservabilityTrace,
    spans: list[ObservabilitySpan],
    llm_calls: list[LLMCallRecord],
    eval_case: EvalCaseResult | None,
) -> str:
    return " ".join(
        [
            trace.trace_id,
            trace.business_event_id or "",
            trace.feature_area,
            trace.agent_name,
            trace.status,
            " ".join(span.node_name for span in spans),
            " ".join(call.llm_call_id for call in llm_calls),
            eval_case.case_id if eval_case else "",
            eval_case.badcase_id if eval_case and eval_case.badcase_id else "",
        ]
    ).lower()


def _trace_search_row(
    *,
    trace: ObservabilityTrace,
    spans: list[ObservabilitySpan],
    llm_calls: list[LLMCallRecord],
    eval_case: EvalCaseResult | None,
) -> dict[str, Any]:
    total_tokens = sum(
        int(call.prompt_tokens or 0) + int(call.completion_tokens or 0)
        for call in llm_calls
    )
    estimated_cost = sum(Decimal(call.estimated_cost or 0) for call in llm_calls)
    return {
        "trace_id": trace.trace_id,
        "started_at": trace.started_at.isoformat(),
        "duration_ms": _row_duration_ms(trace),
        "status": trace.status,
        "feature_area": trace.feature_area,
        "business_run_id": trace.business_event_id or trace.trace_id,
        "agent_name": trace.agent_name,
        "llm_call_count": len(llm_calls),
        "total_tokens": total_tokens,
        "estimated_cost": float(estimated_cost),
        "eval_status": _row_eval_status(eval_case),
        "badcase_status": "OPEN" if eval_case and eval_case.badcase_id else "none",
        "source_revision": str((trace.version_context or {}).get("source_revision") or "unknown"),
        "privacy_class": "redacted_trace",
        "next_node": _row_next_node(trace=trace, spans=spans),
    }


async def search_trace_rows(
    session,
    *,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 25,
    feature_area: str | None = None,
    status: str | None = None,
    eval_status: str | None = None,
    badcase_status: str | None = None,
    privacy_class: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    traces = await list_traces(session, status=status, limit=200)
    rows: list[dict[str, Any]] = []
    normalized_query = (q or "").strip().lower()

    for trace in traces:
        if feature_area and trace.feature_area != feature_area:
            continue
        spans = await list_spans_for_trace(session, trace_id=trace.trace_id)
        llm_calls = await list_llm_calls_for_trace(session, trace_id=trace.trace_id)
        eval_case = await get_eval_case_for_trace(session, trace_id=trace.trace_id)
        row = _trace_search_row(
            trace=trace,
            spans=spans,
            llm_calls=llm_calls,
            eval_case=eval_case,
        )
        if eval_status and row["eval_status"] != eval_status:
            continue
        if badcase_status and row["badcase_status"] != badcase_status:
            continue
        if privacy_class and row["privacy_class"] != privacy_class:
            continue
        if normalized_query and normalized_query not in _trace_search_haystack(
            trace=trace,
            spans=spans,
            llm_calls=llm_calls,
            eval_case=eval_case,
        ):
            continue
        rows.append(row)

    offset = int(cursor or 0) if str(cursor or "").isdigit() else 0
    bounded_limit = max(1, min(limit, 100))
    page = rows[offset : offset + bounded_limit]
    next_offset = offset + bounded_limit
    return page, str(next_offset) if next_offset < len(rows) else None


async def get_trace_hierarchy(session, *, trace_id: str) -> dict[str, Any] | None:
    trace = await get_trace(session, trace_id=trace_id)
    if trace is None:
        return None
    spans = await list_spans_for_trace(session, trace_id=trace_id)
    llm_calls = await list_llm_calls_for_trace(session, trace_id=trace_id)
    eval_case = await get_eval_case_for_trace(session, trace_id=trace_id)
    root_span = next((span for span in spans if span.parent_span_id is None), None)
    return {
        "trace": _trace_search_row(
            trace=trace,
            spans=spans,
            llm_calls=llm_calls,
            eval_case=eval_case,
        ),
        "spans": spans,
        "hierarchy": {
            "root_span_id": root_span.span_id if root_span else None,
            "node_path": [
                span.node_name
                for span in spans
                if span.span_kind == "node"
            ],
            "span_count": len(spans),
            "llm_call_count": len(llm_calls),
        },
        "links": {
            "eval_case_ids": [eval_case.case_result_id] if eval_case else [],
            "badcase_ids": [eval_case.badcase_id] if eval_case and eval_case.badcase_id else [],
        },
    }


async def create_payload(
    session: WriteSession,
    *,
    payload_id: str,
    trace_id: str,
    user_id: UUID,
    span_id: str | None,
    payload_kind: str,
    visibility_mode: str,
    redacted_summary: dict[str, Any],
    shape: dict[str, Any],
    masked_raw: dict[str, Any] | None,
    retention_expires_at: datetime | None,
    secret_scan_status: str = "passed",
) -> ObservabilityPayload:
    row = ObservabilityPayload(
        payload_id=payload_id,
        trace_id=trace_id,
        user_id=user_id,
        span_id=span_id,
        payload_kind=payload_kind,
        visibility_mode=visibility_mode,
        redacted_summary=redacted_summary,
        shape=shape,
        masked_raw=masked_raw,
        retention_expires_at=retention_expires_at,
        secret_scan_status=secret_scan_status,
    )
    session.add(row)
    await session.flush()
    return row


async def get_payload(session, *, payload_id: str) -> ObservabilityPayload | None:
    result = await session.execute(
        select(ObservabilityPayload).where(ObservabilityPayload.payload_id == payload_id)
    )
    return result.scalar_one_or_none()


async def create_llm_call(
    session: WriteSession,
    *,
    llm_call_id: str,
    trace_id: str,
    user_id: UUID,
    span_id: str | None,
    provider: str,
    model: str,
    endpoint: str,
    request_payload_id: str | None,
    response_payload_id: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    safe_curl: str | None,
    started_at: datetime,
    provider_request_id: str | None = None,
    estimated_cost: Decimal | None = None,
    latency_ms: int | None = None,
    retry_count: int = 0,
    status: str = "success",
    ended_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMCallRecord:
    row = LLMCallRecord(
        llm_call_id=llm_call_id,
        trace_id=trace_id,
        user_id=user_id,
        span_id=span_id,
        provider=provider,
        model=model,
        endpoint=endpoint,
        provider_request_id=provider_request_id,
        request_payload_id=request_payload_id,
        response_payload_id=response_payload_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        retry_count=retry_count,
        status=status,
        safe_curl=safe_curl,
        started_at=started_at,
        ended_at=ended_at,
        metadata_json=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def get_llm_call(session, *, llm_call_id: str) -> LLMCallRecord | None:
    result = await session.execute(
        select(LLMCallRecord).where(LLMCallRecord.llm_call_id == llm_call_id)
    )
    return result.scalar_one_or_none()


async def create_tool_operation(
    session: WriteSession,
    *,
    operation_id: str,
    trace_id: str,
    user_id: UUID,
    span_id: str | None,
    tool_name: str,
    status: str,
    started_at: datetime,
    operation_type: str = "tool",
    input_payload_id: str | None = None,
    output_payload_id: str | None = None,
    ended_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> ToolOperationRecord:
    row = ToolOperationRecord(
        operation_id=operation_id,
        trace_id=trace_id,
        user_id=user_id,
        span_id=span_id,
        tool_name=tool_name,
        operation_type=operation_type,
        status=status,
        input_payload_id=input_payload_id,
        output_payload_id=output_payload_id,
        started_at=started_at,
        ended_at=ended_at,
        metadata_json=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def create_eval_run(
    session: WriteSession,
    *,
    eval_run_id: str,
    user_id: UUID,
    name: str,
    status: str,
    started_at: datetime,
    pass_rate: Decimal | None = None,
    completed_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvalRun:
    row = EvalRun(
        eval_run_id=eval_run_id,
        user_id=user_id,
        name=name,
        status=status,
        pass_rate=pass_rate,
        started_at=started_at,
        completed_at=completed_at,
        metadata_json=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def create_eval_case_result(
    session: WriteSession,
    *,
    case_result_id: str,
    eval_run_id: str,
    user_id: UUID,
    case_id: str,
    verdict: str,
    score: Decimal | None = None,
    trace_id: str | None = None,
    llm_call_id: str | None = None,
    badcase_id: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> EvalCaseResult:
    row = EvalCaseResult(
        case_result_id=case_result_id,
        eval_run_id=eval_run_id,
        user_id=user_id,
        case_id=case_id,
        verdict=verdict,
        score=score,
        trace_id=trace_id,
        llm_call_id=llm_call_id,
        badcase_id=badcase_id,
        metrics=metrics or {},
    )
    session.add(row)
    await session.flush()
    return row


async def record_coverage_gap(
    session: WriteSession,
    *,
    feature_area: str,
    flow_name: str,
    severity: str,
    status: str,
    reason: str | None = None,
    accepted_until: datetime | None = None,
) -> ObservabilityCoverageGap:
    row = ObservabilityCoverageGap(
        feature_area=feature_area,
        flow_name=flow_name,
        severity=severity,
        status=status,
        reason=reason,
        accepted_until=accepted_until,
    )
    session.add(row)
    await session.flush()
    return row


async def list_coverage_gaps(session, *, status: str | None = None) -> list[ObservabilityCoverageGap]:
    stmt = select(ObservabilityCoverageGap)
    if status is not None:
        stmt = stmt.where(ObservabilityCoverageGap.status == status)
    stmt = stmt.order_by(ObservabilityCoverageGap.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _gap_value(gap: Any, name: str, default: Any = None) -> Any:
    if isinstance(gap, dict):
        return gap.get(name, default)
    return getattr(gap, name, default)


def build_trace_coverage_rows(
    *,
    observed_surfaces: set[str] | None = None,
    gaps: list[Any] | None = None,
) -> list[dict[str, Any]]:
    observed = observed_surfaces or set()
    gap_by_surface = {
        str(_gap_value(gap, "flow_name", "")): gap
        for gap in (gaps or [])
        if _gap_value(gap, "flow_name")
    }
    rows: list[dict[str, Any]] = []
    for surface in REQ045_TRACE_SURFACES:
        gap = gap_by_surface.get(surface["surface"])
        gap_status = str(_gap_value(gap, "status", "")) if gap else None
        is_open_gap = bool(gap and gap_status.lower() not in {"accepted", "closed"})
        coverage = (
            "gap"
            if is_open_gap
            else "covered"
            if surface["surface"] in observed
            else "unobserved"
        )
        rows.append(
            {
                **surface,
                "coverage": coverage,
                "gap_status": gap_status,
                "gap_reason": _gap_value(gap, "reason") if gap else None,
                "gap_severity": _gap_value(gap, "severity") if gap else None,
            }
        )
    return rows


def _version_context_surfaces(version_context: dict[str, Any] | None) -> set[str]:
    if not version_context:
        return set()
    raw = (
        version_context.get("trace_surfaces")
        or version_context.get("trace_surface")
        or version_context.get("entrypoint")
        or []
    )
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = []
    aliases = {
        "http": "fastapi_http",
        "fastapi": "fastapi_http",
        "websocket": "interview_websocket",
        "ws": "interview_websocket",
        "arq": "arq_worker",
        "worker": "arq_worker",
        "langgraph": "langgraph_nodes",
        "graph": "langgraph_nodes",
        "llm": "llm_invocations",
    }
    return {aliases.get(str(value), str(value)) for value in values}


async def query_trace_coverage_rows(
    session,
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    traces = await list_traces(session, limit=200)
    observed: set[str] = set()
    for trace in traces:
        if environment and trace.environment != environment:
            continue
        observed.update(_version_context_surfaces(trace.version_context or {}))
        spans = await list_spans_for_trace(session, trace_id=trace.trace_id)
        if spans:
            observed.add("langgraph_nodes")
        llm_calls = await list_llm_calls_for_trace(session, trace_id=trace.trace_id)
        if llm_calls:
            observed.add("llm_invocations")

    gaps = await list_coverage_gaps(session, status="open")
    return build_trace_coverage_rows(observed_surfaces=observed, gaps=gaps)


__all__ = [
    "REQ045_TRACE_SURFACES",
    "build_trace_coverage_rows",
    "create_eval_case_result",
    "create_eval_run",
    "create_llm_call",
    "create_payload",
    "create_span",
    "create_tool_operation",
    "create_trace",
    "get_eval_case_for_trace",
    "get_llm_call",
    "get_payload",
    "get_trace",
    "get_trace_hierarchy",
    "list_coverage_gaps",
    "list_llm_calls_for_trace",
    "list_spans_for_trace",
    "list_tool_operations_for_span",
    "list_traces",
    "record_coverage_gap",
    "query_trace_coverage_rows",
    "search_trace_rows",
]
