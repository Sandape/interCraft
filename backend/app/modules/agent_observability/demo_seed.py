from __future__ import annotations

from copy import deepcopy
from typing import Any

GENERATED_AT = "2026-06-29T12:00:00Z"
SUCCESSFUL_TRACE_ID = "req035_trace_success_0001"
FAILED_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
FAILED_LLM_CALL_ID = "llm_1"
FAILED_EVAL_CASE_ID = "case_result_1"
BADCASE_ID = "badcase_1"
EXPIRED_PAYLOAD_ID = "payload_expired_masked_raw"


def build_strong_debug_demo(*, environment: str = "local") -> dict[str, Any]:
    """Return deterministic Strong Debug demo data for local/CI validation.

    The returned structure is intentionally JSON-serializable and free of raw
    resumes, prompts, API keys, or private user text. Seed commands can persist
    this shape later; tests use it today as the canonical REQ-035 fixture.
    """

    demo = {
        "generated_at": GENERATED_AT,
        "environment": environment,
        "users": [
            {
                "user_id": "00000000-0000-7000-8000-000000000035",
                "role": "pm_admin",
                "display_name": "REQ-035 PM Admin",
                "capabilities": ["PM_DASHBOARD_VIEW", "SNAPSHOT_EXPORT"],
            },
            {
                "user_id": "00000000-0000-7000-8000-000000000036",
                "role": "developer_reviewer",
                "display_name": "REQ-035 Developer Reviewer",
                "capabilities": [
                    "TRACE_VIEW",
                    "MASKED_RAW_VIEW",
                    "EVAL_VIEW",
                    "PRIVACY_AUDIT_VIEW",
                ],
            },
        ],
        "successful_trace_id": SUCCESSFUL_TRACE_ID,
        "failed_trace_id": FAILED_TRACE_ID,
        "failed_llm_call_id": FAILED_LLM_CALL_ID,
        "failed_eval_case_id": FAILED_EVAL_CASE_ID,
        "badcase_id": BADCASE_ID,
        "expired_payload_id": EXPIRED_PAYLOAD_ID,
        "dashboard_refresh_at": GENERATED_AT,
        "dashboard_metric_snapshots": [
            {
                "snapshot_id": "metric_complete_active_users",
                "metric_id": "pm.active_users",
                "period_start": "2026-06-28T00:00:00Z",
                "period_end": "2026-06-29T00:00:00Z",
                "value": 128,
                "unit": "count",
                "source_of_truth": "product_events",
                "freshness_at": GENERATED_AT,
                "freshness_target_minutes": 15,
                "refresh_lag_minutes": 0,
                "quality_state": "complete",
                "warnings": [],
            },
            {
                "snapshot_id": "metric_empty_resume_diagnosis",
                "metric_id": "pm.resume_diagnosis",
                "period_start": "2026-06-20T00:00:00Z",
                "period_end": "2026-06-21T00:00:00Z",
                "value": 0,
                "unit": "count",
                "source_of_truth": "product_events",
                "freshness_at": GENERATED_AT,
                "freshness_target_minutes": 15,
                "refresh_lag_minutes": 0,
                "quality_state": "empty",
                "warnings": [],
            },
            {
                "snapshot_id": "metric_partial_mock_interview",
                "metric_id": "pm.mock_interview",
                "period_start": "2026-06-28T00:00:00Z",
                "period_end": "2026-06-29T00:00:00Z",
                "value": 14,
                "unit": "count",
                "source_of_truth": "product_events",
                "freshness_at": "2026-06-29T11:52:00Z",
                "freshness_target_minutes": 15,
                "refresh_lag_minutes": 8,
                "quality_state": "partial",
                "missing_sources": ["interview_outcomes"],
                "warnings": [],
            },
            {
                "snapshot_id": "metric_stale_ai_operations",
                "metric_id": "pm.ai_operations",
                "period_start": "2026-06-28T00:00:00Z",
                "period_end": "2026-06-29T00:00:00Z",
                "value": 240,
                "unit": "count",
                "source_of_truth": "ai_invocation_records",
                "freshness_at": "2026-06-29T11:29:00Z",
                "freshness_target_minutes": 15,
                "refresh_lag_minutes": 31,
                "quality_state": "stale",
                "warnings": ["Source lag exceeded 15 minute target."],
            },
        ],
        "traces": [
            {
                "trace_id": SUCCESSFUL_TRACE_ID,
                "business_run_id": "interview_success_001",
                "feature_area": "interview",
                "agent_name": "interview_supervisor",
                "status": "success",
                "started_at": "2026-06-29T11:45:00Z",
                "duration_ms": 1840,
                "spans": [
                    {
                        "span_id": "span_success_root",
                        "parent_span_id": None,
                        "span_kind": "agent_run",
                        "node_name": "interview_supervisor",
                        "status": "success",
                    }
                ],
                "payloads": [
                    {
                        "payload_id": "payload_success_summary",
                        "visibility_mode": "redacted_trace",
                        "payload_kind": "agent_output",
                        "shape": {"report": "object", "score": "number"},
                        "redacted_summary": "Successful interview report summary.",
                        "retention_state": "active",
                    }
                ],
                "llm_calls": [
                    {
                        "llm_call_id": "llm_success_1",
                        "provider": "openai-compatible",
                        "model": "deepseek-v4-pro",
                        "status": "success",
                        "prompt_tokens": 820,
                        "completion_tokens": 210,
                        "estimated_cost": 0.0028,
                        "provider_request_id": "req_success_provider_001",
                    }
                ],
            },
            {
                "trace_id": FAILED_TRACE_ID,
                "business_run_id": "interview_123",
                "feature_area": "interview",
                "agent_name": "interview_supervisor",
                "status": "error",
                "started_at": GENERATED_AT,
                "duration_ms": 2240,
                "spans": [
                    {
                        "span_id": "span_root",
                        "parent_span_id": None,
                        "span_kind": "agent_run",
                        "node_name": "interview_supervisor",
                        "status": "error",
                    },
                    {
                        "span_id": "span_node_score",
                        "parent_span_id": "span_root",
                        "span_kind": "node",
                        "node_name": "score",
                        "status": "error",
                        "input_payload_id": "payload_req",
                        "output_payload_id": "payload_out",
                    },
                ],
                "payloads": [
                    {
                        "payload_id": "payload_req",
                        "visibility_mode": "redacted_trace",
                        "payload_kind": "llm_request",
                        "shape": {"model": "str", "messages": "list[2]"},
                        "redacted_summary": "Model and message roles only.",
                        "retention_state": "active",
                    },
                    {
                        "payload_id": "payload_out",
                        "visibility_mode": "redacted_trace",
                        "payload_kind": "node_output",
                        "shape": {"score": "number", "feedback": "string"},
                        "redacted_summary": "Output failed schema validation.",
                        "retention_state": "active",
                    },
                    {
                        "payload_id": "payload_resp",
                        "visibility_mode": "redacted_trace",
                        "payload_kind": "llm_response",
                        "shape": {"choices": "list[1]", "usage": "object"},
                        "redacted_summary": "Provider returned nonconforming JSON.",
                        "retention_state": "active",
                    },
                    {
                        "payload_id": "payload_diff",
                        "visibility_mode": "redacted_trace",
                        "payload_kind": "state_diff",
                        "shape": {"score": "changed", "error": "added"},
                        "redacted_summary": "Score removed and validation error added.",
                        "retention_state": "active",
                    },
                    {
                        "payload_id": EXPIRED_PAYLOAD_ID,
                        "visibility_mode": "masked_raw",
                        "payload_kind": "llm_request",
                        "shape": {"messages": "list[2]"},
                        "redacted_summary": "Expired masked raw payload for retention check.",
                        "masked_raw": {
                            "messages": [
                                {"role": "system", "content": "[MASKED:user_text]"},
                                {"role": "user", "content": "[MASKED:user_text]"},
                            ]
                        },
                        "retention_expires_at": "2026-06-15T00:00:00Z",
                        "retention_state": "expired",
                    },
                ],
                "llm_calls": [
                    {
                        "llm_call_id": FAILED_LLM_CALL_ID,
                        "provider": "openai-compatible",
                        "model": "deepseek-v4-pro",
                        "status": "error",
                        "prompt_tokens": 1200,
                        "completion_tokens": 320,
                        "estimated_cost": 0.0042,
                        "provider_request_id": "req_provider_123",
                        "request_payload_id": "payload_req",
                        "response_payload_id": "payload_resp",
                        "retry_count": 1,
                        "latency_ms": 740,
                    }
                ],
                "tool_operations": [
                    {
                        "operation_id": "tool_resume_context_1",
                        "span_id": "span_node_score",
                        "operation_type": "tool",
                        "tool_name": "resume_context_loader",
                        "status": "success",
                        "latency_ms": 38,
                        "input_payload_id": "payload_req",
                        "output_payload_id": "payload_diff",
                    },
                    {
                        "operation_id": "retrieval_rubric_1",
                        "span_id": "span_node_score",
                        "operation_type": "retrieval",
                        "tool_name": "rubric_vector_search",
                        "status": "success",
                        "latency_ms": 52,
                        "input_payload_id": "payload_req",
                        "output_payload_id": "payload_diff",
                    },
                    {
                        "operation_id": "memory_write_failure_1",
                        "span_id": "span_node_score",
                        "operation_type": "memory",
                        "tool_name": "agent_memory.write_failure",
                        "status": "success",
                        "latency_ms": 21,
                        "input_payload_id": "payload_out",
                        "output_payload_id": None,
                    },
                ],
                "eval_case": {
                    "eval_run_id": "eval_run_req035_demo",
                    "case_result_id": FAILED_EVAL_CASE_ID,
                    "case_id": "strong-debug-failed-interview",
                    "verdict": "fail",
                    "trace_id": FAILED_TRACE_ID,
                    "llm_call_id": FAILED_LLM_CALL_ID,
                    "badcase_id": BADCASE_ID,
                    "score": 0.31,
                },
                "badcase": {
                    "badcase_id": BADCASE_ID,
                    "severity": "high",
                    "status": "OPEN",
                    "trace_id": FAILED_TRACE_ID,
                    "llm_call_id": FAILED_LLM_CALL_ID,
                    "category": "schema_validation",
                },
            },
        ],
    }
    return deepcopy(demo)


def build_seed_summary(*, environment: str) -> dict[str, Any]:
    demo = build_strong_debug_demo(environment=environment)
    spans = sum(len(trace.get("spans", [])) for trace in demo["traces"])
    payloads = sum(len(trace.get("payloads", [])) for trace in demo["traces"])
    llm_calls = sum(len(trace.get("llm_calls", [])) for trace in demo["traces"])
    eval_cases = sum(1 for trace in demo["traces"] if trace.get("eval_case"))
    badcases = sum(1 for trace in demo["traces"] if trace.get("badcase"))
    metric_snapshots = demo["dashboard_metric_snapshots"]
    stale_warning_count = sum(
        1
        for snapshot in metric_snapshots
        if snapshot.get("quality_state") == "stale" and snapshot.get("warnings")
    )
    return {
        "environment": environment,
        "seeded": True,
        "generated_at": demo["generated_at"],
        "dashboard_refresh_at": demo["dashboard_refresh_at"],
        "successful_trace_id": demo["successful_trace_id"],
        "failed_trace_id": demo["failed_trace_id"],
        "failed_llm_call_id": demo["failed_llm_call_id"],
        "failed_eval_case_id": demo["failed_eval_case_id"],
        "badcase_id": demo["badcase_id"],
        "expired_payload_id": demo["expired_payload_id"],
        "stale_warning_count": stale_warning_count,
        "counts": {
            "users": len(demo["users"]),
            "traces": len(demo["traces"]),
            "spans": spans,
            "payloads": payloads,
            "llm_calls": llm_calls,
            "eval_cases": eval_cases,
            "badcases": badcases,
            "dashboard_metric_snapshots": len(metric_snapshots),
        },
    }


__all__ = [
    "BADCASE_ID",
    "EXPIRED_PAYLOAD_ID",
    "FAILED_EVAL_CASE_ID",
    "FAILED_LLM_CALL_ID",
    "FAILED_TRACE_ID",
    "SUCCESSFUL_TRACE_ID",
    "build_seed_summary",
    "build_strong_debug_demo",
]
