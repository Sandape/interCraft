from __future__ import annotations

import pytest

from app.modules.badcases.promotion import promote_badcase_to_eval_case


def _badcase() -> dict:
    return {
        "badcaseId": "bc-1",
        "type": "EVAL_REGRESSION",
        "privacyClass": "REDACTED_SUMMARY",
        "redactionStatus": "PASSED",
        "traceId": "a" * 32,
        "runId": "00000000-0000-0000-0000-000000000045",
    }


def test_promote_badcase_to_candidate_eval_case() -> None:
    result = promote_badcase_to_eval_case(
        _badcase(),
        lifecycle="CANDIDATE",
        dataset_version="candidate-v1",
        export_policy_decision_id="export-decision-1",
        reviewer="pm",
        reason="protect regression",
    )

    assert result["case_id"] == "badcase-bc-1"
    assert result["lifecycle"] == "CANDIDATE"
    assert result["dataset_version"] == "candidate-v1"
    assert result["export_policy_decision_id"] == "export-decision-1"
    assert result["status"] == "active"


def test_report_only_promotion_is_non_blocking() -> None:
    result = promote_badcase_to_eval_case(
        _badcase(),
        lifecycle="REPORT_ONLY",
        dataset_version="report-only-v1",
        reviewer="pm",
        reason="observe only",
    )

    assert result["lifecycle"] == "REPORT_ONLY"
    assert result["blocks_merge"] is False


def test_failed_redaction_blocks_candidate_promotion() -> None:
    badcase = {**_badcase(), "redactionStatus": "FAILED"}

    with pytest.raises(ValueError, match="redaction"):
        promote_badcase_to_eval_case(
            badcase,
            lifecycle="CANDIDATE",
            dataset_version="candidate-v1",
            reviewer="pm",
            reason="should fail",
        )
