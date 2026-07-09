from __future__ import annotations

import json

from app.modules.agent_observability.cli import main
from app.modules.agent_observability.demo_seed import build_strong_debug_demo
from tests.fixtures.req035_admin_demo import demo_seed_contract


def test_strong_debug_demo_fixture_covers_required_quickstart_entities() -> None:
    demo = demo_seed_contract()

    users = {user["role"]: user for user in demo["users"]}
    assert "pm_admin" in users
    assert "developer_reviewer" in users
    assert "PM_DASHBOARD_VIEW" in users["pm_admin"]["capabilities"]
    assert "MASKED_RAW_VIEW" in users["developer_reviewer"]["capabilities"]

    traces = {trace["trace_id"]: trace for trace in demo["traces"]}
    assert demo["successful_trace_id"] in traces
    assert demo["failed_trace_id"] in traces
    assert traces[demo["successful_trace_id"]]["status"] == "success"
    assert traces[demo["failed_trace_id"]]["status"] == "error"

    failed_trace = traces[demo["failed_trace_id"]]
    assert failed_trace["spans"]
    assert failed_trace["llm_calls"][0]["llm_call_id"] == demo["failed_llm_call_id"]
    assert failed_trace["eval_case"]["case_result_id"] == demo["failed_eval_case_id"]
    assert failed_trace["badcase"]["badcase_id"] == demo["badcase_id"]

    expired_payload = next(
        payload for payload in failed_trace["payloads"] if payload["payload_id"] == demo["expired_payload_id"]
    )
    assert expired_payload["visibility_mode"] == "masked_raw"
    assert expired_payload["retention_state"] == "expired"

    dashboard_snapshots = demo["dashboard_metric_snapshots"]
    quality_states = {snapshot["quality_state"] for snapshot in dashboard_snapshots}
    assert {"complete", "empty", "partial", "stale"}.issubset(quality_states)
    stale_snapshot = next(
        snapshot for snapshot in dashboard_snapshots if snapshot["quality_state"] == "stale"
    )
    assert stale_snapshot["refresh_lag_minutes"] > stale_snapshot["freshness_target_minutes"]
    assert stale_snapshot["warnings"] == ["Source lag exceeded 15 minute target."]


def test_seed_strong_debug_demo_cli_returns_deterministic_summary(capsys) -> None:
    code = main(["seed-strong-debug-demo", "--env", "local", "--json"])
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    expected = build_strong_debug_demo(environment="local")

    assert code == 0
    assert body["environment"] == "local"
    assert body["seeded"] is True
    assert body["failed_trace_id"] == expected["failed_trace_id"]
    assert body["successful_trace_id"] == expected["successful_trace_id"]
    assert body["counts"] == {
        "users": 2,
        "traces": 2,
        "spans": 3,
        "payloads": 6,
        "llm_calls": 2,
        "eval_cases": 1,
        "badcases": 1,
        "dashboard_metric_snapshots": 4,
    }
    assert body["dashboard_refresh_at"] == "2026-06-29T12:00:00Z"
    assert body["stale_warning_count"] == 1


def test_seed_strong_debug_demo_cli_refuses_production_without_explicit_flag(capsys) -> None:
    code = main(["seed-strong-debug-demo", "--env", "production", "--json"])
    captured = capsys.readouterr()
    body = json.loads(captured.out)

    assert code == 2
    assert body["seeded"] is False
    assert body["error"] == "production seed requires --allow-production-seed"
