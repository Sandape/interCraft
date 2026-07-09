from __future__ import annotations

from app.eval.schemas import Environment, ExportDestination, RepresentationLevel
from app.modules.telemetry_contracts.export_policy import (
    DestinationPolicyInput,
    decide_export_policy,
    scan_for_operational_secrets,
)


def test_secret_scan_detects_nested_keys_and_bearer_values() -> None:
    scan = scan_for_operational_secrets(
        {
            "headers": {"Authorization": "Bearer live-secret"},
            "body": [{"metadata": {"api_key": "sk-live"}}],
        }
    )

    assert scan.has_secret
    assert "headers.Authorization" in scan.paths
    assert "body[0].metadata.api_key" in scan.paths


def test_export_policy_blocks_operational_secrets_for_langsmith() -> None:
    result = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination.LANGSMITH,
            environment=Environment.PRODUCTION,
            requested_level=RepresentationLevel.FULL_CONTENT,
            owner="ai-ops",
            access_scope="langsmith-prod-ai-debuggers",
            retention_days=30,
            allowed_content_classes=("llm_input",),
            payload={"messages": [{"role": "user", "content": "ok"}], "token": "sk-live"},
        )
    )

    assert not result.allowed
    assert result.decision.representation_level == RepresentationLevel.BLOCKED
    assert result.decision.blocked_reason == "operational_secret_detected"
    assert result.secret_scan.paths == ("token",)
