from __future__ import annotations

import pytest

from app.eval.langsmith_sync import LangSmithSyncError, sync_report_to_langsmith
from app.eval.schemas import Environment, ExportDestination, RepresentationLevel
from app.modules.telemetry_contracts.export_policy import (
    DestinationPolicyInput,
    decide_export_policy,
)


class FakeClient:
    def sync_report(self, report: dict, *, project: str) -> dict:
        return {
            "url": f"https://smith.langchain.com/o/test/projects/{project}/runs/{report['runId']}",
            "dataset": report["datasetVersion"],
            "experimentName": f"exp-{report['runId']}",
        }


def _prod_report() -> dict:
    return {
        "runId": "run-prod-1",
        "environment": "PRODUCTION",
        "datasetVersion": "golden-v1",
        "status": "PASSED",
        "caseResults": [],
    }


def test_production_langsmith_sync_requires_export_policy_decision() -> None:
    with pytest.raises(LangSmithSyncError, match="export policy decision"):
        sync_report_to_langsmith(
            _prod_report(),
            mode="require",
            project="intercraft-prod",
            client=FakeClient(),
        )


def test_production_langsmith_full_content_syncs_with_approved_policy() -> None:
    policy = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination.LANGSMITH,
            environment=Environment.PRODUCTION,
            requested_level=RepresentationLevel.FULL_CONTENT,
            owner="ai-ops",
            access_scope="langsmith-prod-ai-debuggers",
            retention_days=30,
            allowed_content_classes=("llm_input", "llm_output", "resume_text"),
            payload=_prod_report(),
        )
    ).decision

    result = sync_report_to_langsmith(
        _prod_report(),
        mode="require",
        project="intercraft-prod",
        client=FakeClient(),
        export_policy_decision=policy,
    )

    assert result.sync_status == "SYNCED"
    assert result.export_policy_decision_id == policy.decision_id
    assert result.url.endswith("/runs/run-prod-1")


def test_blocked_export_policy_prevents_langsmith_sync() -> None:
    policy = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination.LANGSMITH,
            environment=Environment.PRODUCTION,
            requested_level=RepresentationLevel.FULL_CONTENT,
            payload={"api_key": "sk-live"},
        )
    ).decision

    with pytest.raises(LangSmithSyncError, match="blocked"):
        sync_report_to_langsmith(
            _prod_report(),
            mode="require",
            project="intercraft-prod",
            client=FakeClient(),
            export_policy_decision=policy,
        )
