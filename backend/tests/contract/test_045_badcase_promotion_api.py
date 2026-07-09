from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.admin_console.ai_operations.api import post_badcase_promotion
from app.modules.admin_console.ai_operations.schemas import BadcasePromotionRequest


@pytest.mark.anyio
async def test_ai_ops_badcase_promotion_endpoint_returns_eval_case() -> None:
    request = BadcasePromotionRequest(
        badcase={
            "badcaseId": "bc-api",
            "type": "EVAL_REGRESSION",
            "privacyClass": "REDACTED_SUMMARY",
            "redactionStatus": "PASSED",
        },
        lifecycle="REPORT_ONLY",
        dataset_version="report-only-v1",
        reviewer="pm",
        reason="observe only",
    )

    response = await post_badcase_promotion(
        request=request,
        _user_id=uuid4(),
        _cap=True,
    )

    assert response.eval_case["case_id"] == "badcase-bc-api"
    assert response.eval_case["lifecycle"] == "REPORT_ONLY"
    assert response.eval_case["blocks_merge"] is False
