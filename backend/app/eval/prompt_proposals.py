"""Prompt proposal state machine for REQ-045 US6."""
from __future__ import annotations

from app.eval.schemas import (
    PromptImprovementProposalRecord,
    ProposalStatus,
    ProposalType,
)


class NoAutoDeployError(RuntimeError):
    """Raised whenever code attempts to apply a proposal automatically."""


def create_prompt_proposal(
    *,
    source_run_ids: list[str],
    source_case_ids: list[str],
    target_graph: str,
    target_node: str,
    candidate_fingerprint: str,
    expected_impact: str,
) -> PromptImprovementProposalRecord:
    return PromptImprovementProposalRecord(
        status=ProposalStatus.READY_FOR_COMPARISON,
        source_run_ids=source_run_ids,
        source_case_ids=source_case_ids,
        target_graph=target_graph,
        target_node=target_node,
        proposal_type=ProposalType.PROMPT,
        candidate_fingerprint=candidate_fingerprint,
        expected_impact=expected_impact,
    )


def compare_prompt_proposal(
    proposal: PromptImprovementProposalRecord,
    *,
    comparison_run_id: str,
) -> PromptImprovementProposalRecord:
    return proposal.model_copy(
        update={
            "status": ProposalStatus.COMPARED,
            "comparison_run_id": comparison_run_id,
        }
    )


def approve_prompt_proposal(
    proposal: PromptImprovementProposalRecord,
    *,
    owner: str,
) -> PromptImprovementProposalRecord:
    if not proposal.comparison_run_id:
        raise ValueError("prompt proposal approval requires comparison_run_id")
    return proposal.model_copy(
        update={
            "status": ProposalStatus.APPROVED,
            "approval_owner": owner,
        }
    )


def reject_prompt_proposal(
    proposal: PromptImprovementProposalRecord,
    *,
    owner: str,
    reason: str,
) -> PromptImprovementProposalRecord:
    return proposal.model_copy(
        update={
            "status": ProposalStatus.REJECTED,
            "approval_owner": owner,
            "expected_impact": f"{proposal.expected_impact}\nRejected: {reason}",
        }
    )


def apply_prompt_proposal(
    proposal: PromptImprovementProposalRecord,
) -> None:
    raise NoAutoDeployError(
        f"proposal {proposal.proposal_id} cannot auto-deploy; human implementation is required"
    )


def proposal_to_payload(proposal: PromptImprovementProposalRecord) -> dict:
    payload = proposal.model_dump(mode="json")
    return {
        "proposalId": payload["proposal_id"],
        "status": payload["status"],
        "sourceRunIds": payload["source_run_ids"],
        "sourceCaseIds": payload["source_case_ids"],
        "targetGraph": payload["target_graph"],
        "targetNode": payload["target_node"],
        "proposalType": payload["proposal_type"],
        "candidateFingerprint": payload["candidate_fingerprint"],
        "expectedImpact": payload["expected_impact"],
        "comparisonRunId": payload.get("comparison_run_id"),
        "approvalOwner": payload.get("approval_owner"),
    }


def proposal_from_payload(payload: dict) -> PromptImprovementProposalRecord:
    data = {
        "proposal_id": payload.get("proposal_id") or payload.get("proposalId"),
        "status": payload.get("status"),
        "source_run_ids": payload.get("source_run_ids") or payload.get("sourceRunIds") or [],
        "source_case_ids": payload.get("source_case_ids") or payload.get("sourceCaseIds") or [],
        "target_graph": payload.get("target_graph") or payload.get("targetGraph"),
        "target_node": payload.get("target_node") or payload.get("targetNode"),
        "proposal_type": payload.get("proposal_type") or payload.get("proposalType") or "PROMPT",
        "candidate_fingerprint": payload.get("candidate_fingerprint")
        or payload.get("candidateFingerprint"),
        "expected_impact": payload.get("expected_impact") or payload.get("expectedImpact") or "",
        "comparison_run_id": payload.get("comparison_run_id") or payload.get("comparisonRunId"),
        "approval_owner": payload.get("approval_owner") or payload.get("approvalOwner"),
    }
    return PromptImprovementProposalRecord.model_validate(
        {key: value for key, value in data.items() if value is not None}
    )


__all__ = [
    "NoAutoDeployError",
    "apply_prompt_proposal",
    "approve_prompt_proposal",
    "compare_prompt_proposal",
    "create_prompt_proposal",
    "proposal_to_payload",
    "proposal_from_payload",
    "reject_prompt_proposal",
]
