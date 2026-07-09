from __future__ import annotations

import pytest

from app.eval.langsmith_sync import LangSmithSyncError, sync_report_to_langsmith


class FakeClient:
    def sync_report(self, report: dict, *, project: str) -> dict:
        return {
            "url": f"https://smith.langchain.com/o/test/projects/{project}/runs/{report['runId']}",
            "dataset": "golden-v2",
            "experimentName": "exp-abc123",
        }


class FailingClient:
    def sync_report(self, report: dict, *, project: str) -> dict:
        raise RuntimeError("network down")


def test_sync_disabled_returns_disabled() -> None:
    result = sync_report_to_langsmith({"runId": "run-1"}, mode="never", project="p")
    assert result.sync_status == "DISABLED"
    assert result.url == "unavailable"


def test_sync_with_mocked_client_returns_synced() -> None:
    result = sync_report_to_langsmith(
        {"runId": "run-1"},
        mode="auto",
        project="intercraft",
        client=FakeClient(),
    )

    assert result.sync_status == "SYNCED"
    assert result.project == "intercraft"
    assert result.dataset == "golden-v2"
    assert result.url.startswith("https://smith.langchain.com/")


def test_auto_sync_failure_is_non_blocking_status() -> None:
    result = sync_report_to_langsmith(
        {"runId": "run-1"},
        mode="auto",
        project="intercraft",
        client=FailingClient(),
    )

    assert result.sync_status == "FAILED"
    assert "network down" in result.error_message


def test_required_sync_failure_raises() -> None:
    with pytest.raises(LangSmithSyncError):
        sync_report_to_langsmith(
            {"runId": "run-1"},
            mode="require",
            project="intercraft",
            client=FailingClient(),
        )
