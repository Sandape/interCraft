"""Repository helpers for REQ-045 LLM Ops records.

The first implementation keeps helpers primitive and session-friendly. Story
phases can add richer async query methods without changing the shared IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.eval.schemas import (
    ExportPolicyDecisionRecord,
    PromptImprovementProposalRecord,
    TraceRunReference,
)


@dataclass(frozen=True)
class EvalRunIdentity:
    run_id: str
    suite: str
    dataset_version: str
    source_revision: str


@dataclass(frozen=True)
class ExperimentAssignment:
    experiment_id: str
    run_id: str
    variant: str
    subject_id: str | None = None
    metadata: dict[str, Any] | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "variant": self.variant,
            "subject_id": self.subject_id,
            "metadata": dict(self.metadata or {}),
        }


def build_eval_run_identity(
    *,
    run_id: str,
    suite: str,
    dataset_version: str,
    source_revision: str,
) -> EvalRunIdentity:
    return EvalRunIdentity(
        run_id=run_id,
        suite=suite,
        dataset_version=dataset_version,
        source_revision=source_revision,
    )


def normalize_trace_run_ref(
    *,
    run_id: str,
    case_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    artifact_ref: str | None = None,
    langsmith_url: str | None = None,
    entrypoint: str | None = None,
) -> TraceRunReference:
    return TraceRunReference(
        run_id=run_id,
        case_id=case_id,
        trace_id=trace_id,
        span_id=span_id,
        artifact_ref=artifact_ref,
        langsmith_url=langsmith_url,
        entrypoint=entrypoint,
    )


def export_decision_to_row(decision: ExportPolicyDecisionRecord) -> dict[str, Any]:
    payload = decision.model_dump(mode="json")
    payload["allowed_content_classes"] = list(decision.allowed_content_classes)
    return payload


def build_experiment_assignment(
    *,
    experiment_id: str,
    run_id: str,
    variant: str,
    subject_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ExperimentAssignment:
    return ExperimentAssignment(
        experiment_id=experiment_id,
        run_id=run_id,
        variant=variant,
        subject_id=subject_id,
        metadata=metadata or {},
    )


def prompt_proposal_to_row(proposal: PromptImprovementProposalRecord) -> dict[str, Any]:
    return proposal.model_dump(mode="json")


__all__ = [
    "EvalRunIdentity",
    "ExperimentAssignment",
    "build_eval_run_identity",
    "build_experiment_assignment",
    "export_decision_to_row",
    "normalize_trace_run_ref",
    "prompt_proposal_to_row",
]
