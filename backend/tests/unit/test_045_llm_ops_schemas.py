from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.eval import schemas


def test_shared_enums_are_uppercase_contract_values() -> None:
    assert schemas.Environment.PRODUCTION.value == "PRODUCTION"
    assert schemas.ExportDestination.LANGSMITH.value == "LANGSMITH"
    assert schemas.RepresentationLevel.FULL_CONTENT.value == "FULL_CONTENT"
    assert schemas.ExportStatus.PARTIAL.value == "PARTIAL"
    assert schemas.EvalCaseLifecycle.REPORT_ONLY.value == "REPORT_ONLY"


def test_trace_run_ref_accepts_valid_otel_ids_and_displays_unavailable() -> None:
    ref = schemas.TraceRunReference(
        run_id="run-123",
        case_id="case-001",
        trace_id="0" * 32,
        span_id="a" * 16,
        artifact_ref=None,
        langsmith_url=None,
        entrypoint="cli:eval.run",
    )

    assert ref.trace_id == "0" * 32
    assert ref.trace_id_display == "0" * 32
    assert ref.langsmith_url_display == "unavailable"
    assert ref.artifact_ref_display == "unavailable"


def test_trace_run_ref_rejects_malformed_trace_or_span_ids() -> None:
    with pytest.raises(ValidationError):
        schemas.TraceRunReference(run_id="run-1", trace_id="not-hex")

    with pytest.raises(ValidationError):
        schemas.TraceRunReference(run_id="run-1", trace_id="0" * 32, span_id="bad")


def test_eval_run_requires_source_revision_for_ci_and_production() -> None:
    with pytest.raises(ValidationError):
        schemas.EvalRunRecord(
            suite="golden",
            environment=schemas.Environment.CI,
            status=schemas.EvalRunStatus.CREATED,
            dataset_version="golden@v1",
        )

    local = schemas.EvalRunRecord(
        suite="golden",
        environment=schemas.Environment.LOCAL,
        status=schemas.EvalRunStatus.CREATED,
        dataset_version="golden@v1",
    )
    assert local.source_revision == "unavailable"


def test_eval_case_result_candidate_and_report_only_do_not_block() -> None:
    candidate = schemas.EvalCaseResultRecord(
        case_id="case-candidate",
        run_id="run-1",
        lifecycle=schemas.EvalCaseLifecycle.CANDIDATE,
        graph="interview",
        node="score",
        passed=False,
        failure_reasons=["new production badcase"],
    )
    report_only = candidate.model_copy(
        update={"case_id": "case-report", "lifecycle": schemas.EvalCaseLifecycle.REPORT_ONLY}
    )
    golden = candidate.model_copy(
        update={"case_id": "case-golden", "lifecycle": schemas.EvalCaseLifecycle.GOLDEN}
    )

    assert candidate.blocks_merge is False
    assert report_only.blocks_merge is False
    assert golden.blocks_merge is True


def test_export_policy_decision_requires_full_content_langsmith_metadata() -> None:
    with pytest.raises(ValidationError):
        schemas.ExportPolicyDecisionRecord(
            destination=schemas.ExportDestination.LANGSMITH,
            environment=schemas.Environment.PRODUCTION,
            representation_level=schemas.RepresentationLevel.FULL_CONTENT,
            policy_version="req045.v1",
        )

    decision = schemas.ExportPolicyDecisionRecord(
        destination=schemas.ExportDestination.LANGSMITH,
        environment=schemas.Environment.PRODUCTION,
        representation_level=schemas.RepresentationLevel.FULL_CONTENT,
        policy_version="req045.v1",
        owner="ai-platform",
        access_scope="langsmith-prod-project",
        retention_days=30,
        allowed_content_classes=["ai_prompt", "ai_response", "judge_feedback"],
    )

    assert decision.is_external is True
    assert decision.secret_classes_blocked is True


def test_prompt_proposal_cannot_be_approved_without_comparison() -> None:
    with pytest.raises(ValidationError):
        schemas.PromptImprovementProposalRecord(
            status=schemas.ProposalStatus.APPROVED,
            source_run_ids=["run-1"],
            source_case_ids=["case-1"],
            target_graph="interview",
            target_node="score",
            proposal_type=schemas.ProposalType.PROMPT,
            candidate_fingerprint="sha256:abc",
            expected_impact="Improve failure recall.",
            approval_owner="ai-owner",
        )


def test_judge_rubric_blocking_requires_calibration_or_waiver() -> None:
    with pytest.raises(ValidationError):
        schemas.JudgeRubricRecord(
            name="Interview quality",
            version="v1",
            dimensions=["accuracy"],
            scale={"min": 1, "max": 5},
            judge_model="gpt-4.1-mini",
            calibration_status=schemas.JudgeCalibrationStatus.BLOCKING_ENABLED,
            human_label_count=12,
            agreement_rate=0.79,
            owner="ai-owner",
        )
