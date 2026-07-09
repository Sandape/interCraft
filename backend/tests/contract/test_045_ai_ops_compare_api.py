from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.admin_console.ai_operations.api import post_experiment_compare
from app.modules.admin_console.ai_operations.schemas import ExperimentCompareRequest


@pytest.mark.anyio
async def test_ai_ops_compare_endpoint_returns_contract_payload() -> None:
    request = ExperimentCompareRequest(
        baseline={"runId": "baseline", "aggregatePassRate": 0.7},
        candidate={"runId": "candidate", "aggregatePassRate": 0.8},
    )

    response = await post_experiment_compare(
        request=request,
        _user_id=uuid4(),
        _cap=True,
    )

    assert response.baseline_run_id == "baseline"
    assert response.candidate_run_id == "candidate"
    assert response.quality_delta == 0.1
    assert response.recommendation == "candidate_wins"
