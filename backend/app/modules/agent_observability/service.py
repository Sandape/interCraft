from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.modules.agent_observability.capture import CENTRALIZED_AGENT_LLM_FLOWS
from app.modules.agent_observability.curl import build_safe_curl
from app.modules.agent_observability.demo_seed import (
    BADCASE_ID,
    EXPIRED_PAYLOAD_ID,
    FAILED_EVAL_CASE_ID,
    FAILED_LLM_CALL_ID,
    FAILED_TRACE_ID,
    build_strong_debug_demo,
)
from app.modules.agent_observability.payloads import (
    PayloadRevealDenied,
    PayloadRevealExpired,
    PayloadRevealRequest,
    can_reveal_masked_raw,
    mask_sensitive_payload,
    summarize_shape,
)
from app.modules.agent_observability.repository import (
    REQ045_TRACE_SURFACES,
    build_trace_coverage_rows,
)
from app.modules.agent_observability.schemas import (
    CoverageFlow,
    CoverageGap,
    CoverageReport,
    TraceDetailResponse,
    TraceHierarchySummary,
    TraceLinks,
    TraceSearchFilters,
    TraceSearchResponse,
    TraceSearchRow,
    TraceSpan,
    TraceSummary,
)


DEMO_TRACE_ID = FAILED_TRACE_ID
DEMO_LLM_CALL_ID = FAILED_LLM_CALL_ID
DEMO_PAYLOAD_ID = "payload_req"


def build_coverage_report(
    *,
    environment: str,
    gaps: list[dict[str, Any]] | None = None,
) -> CoverageReport:
    covered = [
        CoverageFlow(feature_area=_feature_area_for_flow(flow), flow_name=flow)
        for flow in CENTRALIZED_AGENT_LLM_FLOWS
    ]
    return CoverageReport(
        environment=environment,
        covered_flows=covered,
        gaps=[CoverageGap.model_validate(gap) for gap in (gaps or [])],
    )


def build_req045_trace_coverage_summary(
    *,
    environment: str,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    coverage_rows = rows or build_trace_coverage_rows(
        observed_surfaces={surface["surface"] for surface in REQ045_TRACE_SURFACES},
        gaps=[],
    )
    covered_count = sum(1 for row in coverage_rows if row["coverage"] == "covered")
    gap_count = sum(1 for row in coverage_rows if row["coverage"] == "gap")
    unobserved_count = sum(1 for row in coverage_rows if row["coverage"] == "unobserved")
    return {
        "environment": environment,
        "generated_at": datetime.now(UTC).isoformat(),
        "covered_count": covered_count,
        "gap_count": gap_count,
        "unobserved_count": unobserved_count,
        "surfaces": coverage_rows,
    }


def _feature_area_for_flow(flow: str) -> str:
    if "interview" in flow:
        return "interview"
    if "resume" in flow:
        return "resume"
    if "error" in flow:
        return "error_coach"
    return "coach"


def _trace_tokens(trace: dict[str, Any]) -> int:
    return sum(
        int(call.get("prompt_tokens", 0)) + int(call.get("completion_tokens", 0))
        for call in trace.get("llm_calls", [])
    )


def _trace_cost(trace: dict[str, Any]) -> float:
    return round(
        sum(float(call.get("estimated_cost", 0.0) or 0.0) for call in trace.get("llm_calls", [])),
        6,
    )


def _trace_eval_status(trace: dict[str, Any]) -> str:
    eval_case = trace.get("eval_case")
    if not eval_case:
        return "not_run"
    return "failed" if str(eval_case.get("verdict", "")).lower() in {"fail", "failed"} else "passed"


def _trace_badcase_status(trace: dict[str, Any]) -> str:
    badcase = trace.get("badcase")
    return str(badcase.get("status", "none")) if badcase else "none"


def _trace_privacy_class(trace: dict[str, Any]) -> str:
    if any(payload.get("visibility_mode") == "masked_raw" for payload in trace.get("payloads", [])):
        return "sensitive_user_content"
    return "internal"


def _trace_next_node(trace: dict[str, Any]) -> str:
    if trace.get("status") == "success":
        return "complete"
    for span in trace.get("spans", []):
        if span.get("span_kind") == "node" and span.get("status") == "error":
            return str(span.get("node_name") or span.get("span_id"))
    return "unknown"


def _trace_row(trace: dict[str, Any]) -> TraceSearchRow:
    return TraceSearchRow(
        trace_id=str(trace["trace_id"]),
        started_at=str(trace["started_at"]),
        duration_ms=int(trace.get("duration_ms", 0)),
        status=str(trace.get("status", "unknown")),
        feature_area=str(trace.get("feature_area", "unknown")),
        business_run_id=str(trace.get("business_run_id", "")),
        agent_name=str(trace.get("agent_name", "unknown")),
        llm_call_count=len(trace.get("llm_calls", [])),
        total_tokens=_trace_tokens(trace),
        estimated_cost=_trace_cost(trace),
        eval_status=_trace_eval_status(trace),
        badcase_status=_trace_badcase_status(trace),
        source_revision="unknown",
        privacy_class=_trace_privacy_class(trace),
        next_node=_trace_next_node(trace),
    )


def _matches_trace_query(row: TraceSearchRow, trace: dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        [
            row.trace_id,
            row.business_run_id,
            row.agent_name,
            row.feature_area,
            row.status,
            row.eval_status,
            row.badcase_status,
            " ".join(str(span.get("node_name") or span.get("span_id")) for span in trace.get("spans", [])),
            " ".join(str(call.get("llm_call_id")) for call in trace.get("llm_calls", [])),
            str(trace.get("badcase", {}).get("badcase_id", "")),
        ]
    ).lower()
    return query.lower() in haystack


def search_traces(filters: TraceSearchFilters | None = None) -> dict[str, Any]:
    """Search traces. REQ-061 T170: disable in-memory demo when seeded fallbacks off."""
    from app.modules.admin_console.production_fallbacks import seed_fallbacks_disabled

    filters = filters or TraceSearchFilters()
    if seed_fallbacks_disabled():
        response = TraceSearchResponse(
            items=[],
            next_cursor=None,
            freshness_at="unavailable",
        )
        return response.model_dump(mode="json")

    demo = build_strong_debug_demo(environment="local")
    traces = sorted(demo["traces"], key=lambda item: str(item.get("started_at", "")), reverse=True)

    rows: list[tuple[TraceSearchRow, dict[str, Any]]] = []
    for trace in traces:
        row = _trace_row(trace)
        if filters.status and row.status != filters.status:
            continue
        if filters.feature_area and row.feature_area != filters.feature_area:
            continue
        if filters.eval_status and row.eval_status != filters.eval_status:
            continue
        if filters.badcase_status and row.badcase_status != filters.badcase_status:
            continue
        if filters.privacy_class and row.privacy_class != filters.privacy_class:
            continue
        if filters.q and not _matches_trace_query(row, trace, filters.q):
            continue
        rows.append((row, trace))

    offset = int(filters.cursor or 0) if str(filters.cursor or "").isdigit() else 0
    limit = filters.limit
    page = rows[offset : offset + limit]
    next_offset = offset + limit
    response = TraceSearchResponse(
        items=[row for row, _trace in page],
        next_cursor=str(next_offset) if next_offset < len(rows) else None,
        freshness_at=datetime.now(UTC).isoformat(),
    )
    return response.model_dump(mode="json")


def _trace_by_id(trace_id: str) -> dict[str, Any]:
    demo = build_strong_debug_demo(environment="local")
    for trace in demo["traces"]:
        if trace["trace_id"] == trace_id:
            return trace
    raise KeyError(trace_id)


def get_trace_detail(trace_id: str) -> dict[str, Any]:
    trace = _trace_by_id(trace_id)
    row = _trace_row(trace)
    spans = [
        TraceSpan(
            span_id=str(span["span_id"]),
            parent_span_id=span.get("parent_span_id"),
            span_kind=str(span.get("span_kind", "node")),
            name=str(span.get("node_name") or span.get("span_id")),
            node_name=span.get("node_name"),
            status=str(span.get("status", "unknown")),
            duration_ms=int(span.get("duration_ms", row.duration_ms if span.get("parent_span_id") is None else 0)),
            input_payload_id=span.get("input_payload_id"),
            output_payload_id=span.get("output_payload_id"),
            state_diff_payload_id=span.get("state_diff_payload_id"),
        )
        for span in trace.get("spans", [])
    ]
    node_path = [span.node_name or span.name for span in spans if span.span_kind == "node"]
    root_span = next((span for span in spans if span.parent_span_id is None), None)
    eval_case = trace.get("eval_case")
    badcase = trace.get("badcase")
    response = TraceDetailResponse(
        trace=TraceSummary(
            trace_id=row.trace_id,
            business_run_id=row.business_run_id,
            feature_area=row.feature_area,
            status=row.status,
            started_at=row.started_at,
            duration_ms=row.duration_ms,
            total_tokens=row.total_tokens,
            estimated_cost=row.estimated_cost,
            eval_status=row.eval_status,
        ),
        spans=spans,
        hierarchy=TraceHierarchySummary(
            root_span_id=root_span.span_id if root_span else None,
            node_path=node_path,
            span_count=len(spans),
            llm_call_count=row.llm_call_count,
        ),
        links=TraceLinks(
            eval_case_ids=[eval_case["case_result_id"]] if eval_case else [],
            badcase_ids=[badcase["badcase_id"]] if badcase else [],
        ),
        visibility_mode="redacted_trace",
    )
    return response.model_dump(mode="json")


def _demo_payload_by_id(trace: dict[str, Any], payload_id: str | None) -> dict[str, Any] | None:
    if not payload_id:
        return None
    for payload in trace.get("payloads", []):
        if payload.get("payload_id") == payload_id:
            return payload
    return None


def _payload_summary(payload: dict[str, Any] | None, *, fallback_id: str) -> dict[str, Any]:
    if payload is None:
        return {
            "payload_id": fallback_id,
            "visibility_mode": "redacted_trace",
            "shape": {},
            "redacted_summary": "No payload metadata recorded.",
        }
    return {
        "payload_id": payload["payload_id"],
        "visibility_mode": payload.get("visibility_mode", "redacted_trace"),
        "shape": payload.get("shape", {}),
        "redacted_summary": payload.get("redacted_summary", ""),
    }


def _tool_operations_for_span(trace: dict[str, Any], span_id: str) -> list[dict[str, Any]]:
    return [
        {
            "operation_id": operation["operation_id"],
            "operation_type": operation["operation_type"],
            "tool_name": operation["tool_name"],
            "status": operation["status"],
            "latency_ms": operation.get("latency_ms", 0),
            "input_payload_id": operation.get("input_payload_id"),
            "output_payload_id": operation.get("output_payload_id"),
        }
        for operation in trace.get("tool_operations", [])
        if operation.get("span_id") == span_id
    ]


def get_node_detail(span_id: str) -> dict[str, Any]:
    demo = build_strong_debug_demo(environment="local")
    for trace in demo["traces"]:
        span = next(
            (
                item
                for item in trace.get("spans", [])
                if item.get("span_id") == span_id
            ),
            None,
        )
        if span is None:
            continue
        input_payload = _demo_payload_by_id(trace, span.get("input_payload_id"))
        output_payload = _demo_payload_by_id(trace, span.get("output_payload_id"))
        state_payload = _demo_payload_by_id(trace, span.get("state_diff_payload_id") or "payload_diff")
        operations = _tool_operations_for_span(trace, span_id)
        return {
            "span_id": span_id,
            "trace_id": trace["trace_id"],
            "node_name": span.get("node_name", "unknown"),
            "status": span.get("status", "unknown"),
            "duration_ms": int(span.get("duration_ms", trace.get("duration_ms", 0))),
            "input": _payload_summary(input_payload, fallback_id=span.get("input_payload_id") or "payload_in"),
            "output": _payload_summary(output_payload, fallback_id=span.get("output_payload_id") or "payload_out"),
            "state_diff": _payload_summary(state_payload, fallback_id="payload_diff"),
            "llm_calls": [
                call["llm_call_id"]
                for call in trace.get("llm_calls", [])
                if call.get("request_payload_id") == span.get("input_payload_id")
                or span.get("span_id") == "span_node_score"
            ],
            "tool_operations": operations,
            "emitted_events": ["node.completed"] if span.get("status") == "success" else ["node.failed"],
            "next_step": "Open linked eval case and badcase." if trace.get("badcase") else "Trace complete.",
            "errors": ["schema_validation_failed"] if span.get("status") == "error" else [],
            "retry_count": max(
                [int(call.get("retry_count", 0) or 0) for call in trace.get("llm_calls", [])],
                default=0,
            ),
        }
    return {
        "span_id": span_id,
        "trace_id": DEMO_TRACE_ID,
        "node_name": "score",
        "status": "error",
        "duration_ms": 740,
        "input": {
            "payload_id": DEMO_PAYLOAD_ID,
            "visibility_mode": "redacted_trace",
            "shape": {"answers": "array[5]", "rubric": "object"},
            "redacted_summary": "5 answers and scoring rubric present",
        },
        "output": {
            "payload_id": "payload_out",
            "visibility_mode": "redacted_trace",
            "shape": {"score": "number", "feedback": "string"},
            "redacted_summary": "Output failed schema validation",
        },
        "state_diff": {
            "payload_id": "payload_diff",
            "shape": {"score": "changed", "error": "added"},
        },
        "llm_calls": [DEMO_LLM_CALL_ID],
        "tool_operations": [],
    }


def get_llm_call_detail(llm_call_id: str) -> dict[str, Any]:
    return {
        "llm_call_id": llm_call_id,
        "trace_id": DEMO_TRACE_ID,
        "provider": "openai-compatible",
        "endpoint": "/v1/chat/completions",
        "http_method": "POST",
        "model_requested": "deepseek-v4-pro",
        "model_returned": "deepseek-v4-pro",
        "parameters": {
            "temperature": 0.2,
            "stream": True,
            "response_format": "json_schema",
        },
        "usage": {
            "prompt_tokens": 1200,
            "completion_tokens": 320,
            "cache_tokens": 0,
            "reasoning_tokens": 0,
            "estimated_cost": 0.0042,
        },
        "timing": {
            "latency_ms": 740,
            "time_to_first_token_ms": 210,
            "stream_chunk_count": 18,
        },
        "status": "error",
        "finish_reason": None,
        "provider_request_id": "req_provider_123",
        "request_payload_id": DEMO_PAYLOAD_ID,
        "response_payload_id": "payload_resp",
    }


async def reveal_payload(
    *,
    payload_id: str,
    actor_user_id: str,
    reason: str,
) -> dict[str, Any]:
    payload = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "candidate resume text"},
        ],
    }
    now = datetime.now(UTC)
    retention_expires_at = (
        now - timedelta(seconds=1)
        if payload_id == EXPIRED_PAYLOAD_ID
        else now + timedelta(days=1)
    )
    request = PayloadRevealRequest(
        payload_id=uuid4(),
        actor_id=UUID(actor_user_id),
        role_labels=set(),
        capabilities=set(),
        reason=reason,
        now=now,
        retention_expires_at=retention_expires_at,
    )
    try:
        can_reveal_masked_raw(request)
    except (PayloadRevealDenied, PayloadRevealExpired):
        _audit_stub(actor_user_id=actor_user_id, action="payload.reveal", target_id=payload_id, reason=reason, decision="denied")
        raise

    audit_id = _audit_stub(actor_user_id=actor_user_id, action="payload.reveal", target_id=payload_id, reason=reason, decision="allowed")
    return {
        "payload_id": payload_id,
        "visibility_mode": "masked_raw",
        "shape": summarize_shape(payload),
        "masked_raw": mask_sensitive_payload(payload),
        "audit_id": audit_id,
    }


async def get_llm_curl(
    *,
    llm_call_id: str,
    actor_user_id: str,
    reason: str,
    include_masked_body: bool = False,
) -> dict[str, Any]:
    del include_masked_body

    safe = build_safe_curl(
        method="POST",
        base_url="https://api.example.com",
        endpoint="/v1/chat/completions",
        headers={
            "Authorization": "Bearer live-secret",
            "Content-Type": "application/json",
        },
        body={"model": "deepseek-v4-pro", "messages": "[REDACTED]"},
        provider="openai-compatible",
        model="deepseek-v4-pro",
        trace_id=DEMO_TRACE_ID,
        attempt=1,
    )
    audit_id = _audit_stub(actor_user_id=actor_user_id, action="curl.view", target_id=llm_call_id, reason=reason, decision="allowed")
    return {
        "llm_call_id": llm_call_id,
        "visibility_mode": "redacted_trace",
        "curl": safe.curl,
        "redacted_headers": safe.redacted_headers,
        "audit_id": audit_id,
    }


def _audit_stub(*, actor_user_id: str, action: str, target_id: str, reason: str, decision: str) -> str:
    """REQ-051 minimal audit stub — returns a synthetic audit_id.

    The old ``record_audit_event()`` was removed when the 6-role RBAC
    matrix was deleted (``admin_console.auth._ROLE_GRANTS``).  Until a
    real audit sink lands, return a deterministic id so the API shape
    stays backward-compatible.
    """
    audit_id = str(uuid4())
    return audit_id


def list_eval_runs() -> dict[str, Any]:
    demo = build_strong_debug_demo(environment="local")
    failed_trace = next(trace for trace in demo["traces"] if trace["trace_id"] == FAILED_TRACE_ID)
    llm = failed_trace["llm_calls"][0]
    return {
        "items": [
            {
                "eval_run_id": "eval_run_req035_demo",
                "suite": "golden",
                "environment": "local",
                "dataset_id": "strong-debug-demo",
                "source_revision": "unknown",
                "prompt_version": "prompt_req035_demo",
                "rubric_version": "rubric_v1",
                "model": llm["model"],
                "status": "failed",
                "pass_rate": 0.5,
                "avg_score": 0.66,
                "failed_case_count": 1,
                "total_tokens": llm["prompt_tokens"] + llm["completion_tokens"],
                "estimated_cost": llm["estimated_cost"],
                "started_at": "2026-06-29T12:00:00Z",
                "completed_at": "2026-06-29T12:02:00Z",
            }
        ],
        "next_cursor": None,
    }


def get_eval_run(eval_run_id: str) -> dict[str, Any]:
    case = get_eval_case(FAILED_EVAL_CASE_ID)
    return {
        "eval_run": {
            "eval_run_id": eval_run_id,
            "suite": "golden",
            "status": "failed",
            "pass_rate": 0.5,
            "avg_score": 0.66,
        },
        "cases": [
            {
                "case_result_id": case["case_result_id"],
                "case_id": case["case_id"],
                "status": case["status"],
                "score": case["score"],
                "score_dimensions": case["score_dimensions"],
                "trace_id": case["trace_id"],
                "badcase_id": case["badcase_id"],
                "failure_reason": "Expected valid scoring JSON but schema validation failed.",
            }
        ],
    }


def get_eval_case(case_result_id: str) -> dict[str, Any]:
    return {
        "case_result_id": case_result_id,
        "case_id": "strong-debug-failed-interview",
        "status": "failed",
        "score": 0.31,
        "score_dimensions": {
            "task_success": 0.0,
            "format_validity": 0.0,
            "safety": 1.0,
            "privacy_leakage": 1.0,
            "tool_call_correctness": None,
        },
        "expected_summary": "Interview score node should return schema-valid JSON.",
        "actual_summary": "Provider output omitted required scoring fields.",
        "trace_id": FAILED_TRACE_ID,
        "llm_call_id": FAILED_LLM_CALL_ID,
        "badcase_id": BADCASE_ID,
        "evaluator": {
            "evaluator_id": "rubric_interview_v1",
            "type": "rubric",
            "rubric_version": "rubric_v1",
            "judge_prompt_version": "judge_v1",
        },
    }


def get_latest_eval_gate() -> dict[str, Any]:
    return {
        "gate": "pr_eval",
        "status": "failed",
        "eval_run_id": "eval_run_req035_demo",
        "source_revision": "unknown",
        "failed_case_count": 1,
        "override": {
            "status": "none",
            "pm_approver": None,
            "technical_approver": None,
        },
    }


__all__ = [
    "DEMO_LLM_CALL_ID",
    "DEMO_PAYLOAD_ID",
    "DEMO_TRACE_ID",
    "build_coverage_report",
    "build_req045_trace_coverage_summary",
    "get_eval_case",
    "get_eval_run",
    "get_latest_eval_gate",
    "get_llm_call_detail",
    "get_llm_curl",
    "get_node_detail",
    "get_trace_detail",
    "list_eval_runs",
    "reveal_payload",
    "search_traces",
]
