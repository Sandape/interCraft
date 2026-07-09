from __future__ import annotations

from app.modules.agent_observability.repository import build_trace_coverage_rows
from app.modules.agent_observability.service import build_req045_trace_coverage_summary


def test_trace_coverage_rows_mark_unobserved_and_open_gaps() -> None:
    rows = build_trace_coverage_rows(
        observed_surfaces={"fastapi_http", "llm_invocations"},
        gaps=[
            {
                "flow_name": "arq_worker",
                "status": "open",
                "severity": "medium",
                "reason": "worker hook not deployed",
            }
        ],
    )

    by_surface = {row["surface"]: row for row in rows}
    assert by_surface["fastapi_http"]["coverage"] == "covered"
    assert by_surface["llm_invocations"]["coverage"] == "covered"
    assert by_surface["arq_worker"]["coverage"] == "gap"
    assert by_surface["interview_websocket"]["coverage"] == "unobserved"


def test_req045_service_summary_defaults_to_five_covered_surfaces() -> None:
    summary = build_req045_trace_coverage_summary(environment="local")

    assert summary["environment"] == "local"
    assert summary["covered_count"] == 5
    assert summary["gap_count"] == 0
    assert summary["unobserved_count"] == 0
    assert {row["surface"] for row in summary["surfaces"]} == {
        "fastapi_http",
        "interview_websocket",
        "arq_worker",
        "langgraph_nodes",
        "llm_invocations",
    }
