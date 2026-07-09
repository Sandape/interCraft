from __future__ import annotations

from app.eval.prompt_proposals import (
    approve_prompt_proposal,
    compare_prompt_proposal,
    create_prompt_proposal,
    reject_prompt_proposal,
)
from app.eval.schemas import ProposalStatus


def test_prompt_proposal_create_compare_approve_flow() -> None:
    proposal = create_prompt_proposal(
        source_run_ids=["run-1"],
        source_case_ids=["case-1"],
        target_graph="interview",
        target_node="score",
        candidate_fingerprint="sha256:candidate",
        expected_impact="Improve rubric fidelity",
    )
    compared = compare_prompt_proposal(proposal, comparison_run_id="cmp-1")
    approved = approve_prompt_proposal(compared, owner="pm")

    assert proposal.status == ProposalStatus.READY_FOR_COMPARISON
    assert compared.status == ProposalStatus.COMPARED
    assert approved.status == ProposalStatus.APPROVED
    assert approved.approval_owner == "pm"


def test_prompt_proposal_rejects_without_apply() -> None:
    proposal = create_prompt_proposal(
        source_run_ids=["run-1"],
        source_case_ids=["case-1"],
        target_graph="interview",
        target_node="score",
        candidate_fingerprint="sha256:candidate",
        expected_impact="Improve rubric fidelity",
    )
    rejected = reject_prompt_proposal(proposal, owner="pm", reason="not enough evidence")

    assert rejected.status == ProposalStatus.REJECTED
    assert rejected.approval_owner == "pm"
