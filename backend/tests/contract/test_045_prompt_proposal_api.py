from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.admin_console.ai_operations.api import post_prompt_proposal
from app.modules.admin_console.ai_operations.schemas import PromptProposalCreateRequest


@pytest.mark.anyio
async def test_ai_ops_prompt_proposal_create_endpoint() -> None:
    request = PromptProposalCreateRequest(
        source_run_ids=["run-1"],
        source_case_ids=["case-1"],
        target_graph="interview",
        target_node="score",
        candidate_fingerprint="sha256:candidate",
        expected_impact="Improve score fidelity",
    )

    response = await post_prompt_proposal(
        request=request,
        _user_id=uuid4(),
        _cap=True,
    )

    assert response.status == "READY_FOR_COMPARISON"
    assert response.target_graph == "interview"
    assert response.target_node == "score"
