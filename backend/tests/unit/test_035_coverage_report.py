from __future__ import annotations

from app.modules.agent_observability.capture import CENTRALIZED_AGENT_LLM_FLOWS
from app.modules.agent_observability.service import build_coverage_report


def test_coverage_report_lists_centralized_flows_as_covered() -> None:
    report = build_coverage_report(environment="production", gaps=[])

    covered = {item.flow_name for item in report.covered_flows}
    assert set(CENTRALIZED_AGENT_LLM_FLOWS).issubset(covered)
    assert report.high_severity_gap_count == 0


def test_coverage_report_counts_open_high_severity_gaps() -> None:
    report = build_coverage_report(
        environment="production",
        gaps=[
            {
                "feature_area": "legacy",
                "flow_name": "direct_provider_call_example",
                "reason": "direct_provider_call",
                "severity": "high",
                "status": "open",
            }
        ],
    )

    assert report.gap_count == 1
    assert report.high_severity_gap_count == 1
