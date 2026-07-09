from __future__ import annotations

import pytest

from app.eval.prompt_proposals import NoAutoDeployError, apply_prompt_proposal, create_prompt_proposal


def test_prompt_proposal_cannot_auto_deploy() -> None:
    proposal = create_prompt_proposal(
        source_run_ids=["run-1"],
        source_case_ids=["case-1"],
        target_graph="interview",
        target_node="score",
        candidate_fingerprint="sha256:candidate",
        expected_impact="Improve rubric fidelity",
    )

    with pytest.raises(NoAutoDeployError):
        apply_prompt_proposal(proposal)
