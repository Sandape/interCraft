from __future__ import annotations

from app.eval.schemas import Environment, ExportDestination, RepresentationLevel
from app.modules.telemetry_contracts.export_policy import (
    DestinationPolicyInput,
    decide_export_policy,
)


def test_production_langsmith_full_content_requires_policy_metadata() -> None:
    result = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination.LANGSMITH,
            environment=Environment.PRODUCTION,
            requested_level=RepresentationLevel.FULL_CONTENT,
            payload={"messages": [{"role": "user", "content": "resume text"}]},
        )
    )

    assert not result.allowed
    assert result.decision.representation_level == RepresentationLevel.BLOCKED
    assert result.decision.blocked_reason is not None
    assert "missing_full_content_policy_metadata" in result.decision.blocked_reason


def test_production_langsmith_full_content_allowed_with_complete_metadata() -> None:
    result = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination.LANGSMITH,
            environment=Environment.PRODUCTION,
            requested_level=RepresentationLevel.FULL_CONTENT,
            owner="ai-ops",
            access_scope="langsmith-prod-ai-debuggers",
            retention_days=30,
            allowed_content_classes=("resume_text", "llm_input", "llm_output"),
            payload={"messages": [{"role": "user", "content": "resume text"}]},
        )
    )

    assert result.allowed
    assert result.decision.representation_level == RepresentationLevel.FULL_CONTENT
    assert result.decision.owner == "ai-ops"
    assert result.decision.access_scope == "langsmith-prod-ai-debuggers"
    assert result.decision.retention_days == 30


def test_generic_otlp_full_content_is_downgraded_to_redacted() -> None:
    result = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination.OTLP_GENERIC,
            environment=Environment.PRODUCTION,
            requested_level=RepresentationLevel.FULL_CONTENT,
            payload={"messages": [{"role": "user", "content": "raw answer"}]},
        )
    )

    assert result.allowed
    assert result.decision.representation_level == RepresentationLevel.REDACTED
