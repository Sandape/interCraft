from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.agent_observability.payloads import (
    PayloadRevealDenied,
    PayloadRevealExpired,
    PayloadRevealRequest,
    can_reveal_masked_raw,
    mask_sensitive_payload,
    summarize_shape,
)
from app.modules.telemetry_contracts.redaction import validate_masked_raw_payload


def test_shape_summary_never_keeps_raw_leaf_values() -> None:
    shape = summarize_shape(
        {
            "messages": [
                {"role": "system", "content": "private prompt"},
                {"role": "user", "content": "candidate resume"},
            ],
            "temperature": 0.2,
        }
    )

    assert shape == {
        "messages": "array[2]",
        "temperature": "number",
    }


def test_mask_sensitive_payload_masks_secrets_and_user_text() -> None:
    masked = mask_sensitive_payload(
        {
            "Authorization": "Bearer live-secret",
            "api_key": "sk-live-secret",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "resume text"},
            ],
        }
    )

    assert masked["Authorization"] == "[MASKED_SECRET]"
    assert masked["api_key"] == "[MASKED_SECRET]"
    assert masked["messages"][0]["content"] == "[MASKED_SYSTEM_PROMPT]"
    assert masked["messages"][1]["content"] == "[MASKED_USER_TEXT]"


def test_validate_masked_raw_payload_accepts_mask_placeholders() -> None:
    violations = validate_masked_raw_payload(
        {
            "Authorization": "[MASKED_SECRET]",
            "messages": [
                {"role": "system", "content": "[MASKED_SYSTEM_PROMPT]"},
                {"role": "user", "content": "[MASKED_USER_TEXT]"},
            ],
        }
    )

    assert violations == []


def test_validate_masked_raw_payload_rejects_unmasked_secrets_and_user_text() -> None:
    violations = validate_masked_raw_payload(
        {
            "Authorization": "Bearer live-secret",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "candidate resume text"},
            ],
            "nested": {"api_key": "sk-live-secret"},
        }
    )

    assert set(violations) == {
        "Authorization",
        "messages[0].content",
        "messages[1].content",
        "nested.api_key",
    }


def test_masked_raw_reveal_requires_role_and_reason() -> None:
    request = PayloadRevealRequest(
        payload_id=uuid4(),
        actor_id=uuid4(),
        role_labels={"pm"},
        capabilities={"PM_DASHBOARD_VIEW"},
        reason="Investigating a failed eval",
        now=datetime(2026, 6, 29, tzinfo=UTC),
        retention_expires_at=datetime(2026, 6, 30, tzinfo=UTC),
    )

    with pytest.raises(PayloadRevealDenied):
        can_reveal_masked_raw(request)

    request.role_labels.add("developer")
    request.capabilities.add("MASKED_RAW_VIEW")
    request.reason = " "

    with pytest.raises(PayloadRevealDenied):
        can_reveal_masked_raw(request)


def test_masked_raw_reveal_denies_expired_payload() -> None:
    request = PayloadRevealRequest(
        payload_id=uuid4(),
        actor_id=uuid4(),
        role_labels={"reviewer"},
        capabilities={"MASKED_RAW_VIEW"},
        reason="Reproducing a node failure",
        now=datetime(2026, 6, 29, tzinfo=UTC),
        retention_expires_at=datetime(2026, 6, 29, tzinfo=UTC) - timedelta(seconds=1),
    )

    with pytest.raises(PayloadRevealExpired):
        can_reveal_masked_raw(request)


def test_masked_raw_reveal_allows_developer_or_reviewer_before_expiry() -> None:
    request = PayloadRevealRequest(
        payload_id=uuid4(),
        actor_id=uuid4(),
        role_labels={"reviewer"},
        capabilities={"MASKED_RAW_VIEW"},
        reason="Reproducing a node failure",
        now=datetime(2026, 6, 29, tzinfo=UTC),
        retention_expires_at=datetime(2026, 6, 30, tzinfo=UTC),
    )

    decision = can_reveal_masked_raw(request)

    assert decision.allowed is True
    assert decision.visibility_mode == "masked_raw"
