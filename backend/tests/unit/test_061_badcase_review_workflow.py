"""REQ-061 T127 — Bad Case typed review workflow / FSM unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.badcases.service import (
    BadcaseCommandError,
    TYPED_ACTION_TYPES,
    evaluate_sla_status,
    missing_closure_fields,
)


REQUIRED_ACTIONS = {
    "CLASSIFY",
    "ASSIGN",
    "MERGE",
    "ADD_NOTE",
    "ESCALATE_INCIDENT",
    "RECORD_POINT_TREATMENT",
    "PROMOTE_REGRESSION",
    "MARK_UNREPRODUCIBLE",
    "CLOSE",
    "INTAKE",
}


def test_typed_action_set_covers_openapi_commands() -> None:
    assert REQUIRED_ACTIONS == set(TYPED_ACTION_TYPES)


def test_missing_closure_fields_lists_absent_evidence() -> None:
    missing = missing_closure_fields(
        {
            "fix_or_policy_version": "policy-v2",
            "regression_case_ref": None,
            "passing_evaluation_ref": "",
            "point_treatment_ref": "pt-1",
            "user_notification_ref": "n-1",
        }
    )
    assert "regression_case_ref" in missing
    assert "passing_evaluation_ref" in missing
    assert "fix_or_policy_version" not in missing


def test_p0_sla_breached_without_owner() -> None:
    created = datetime.now(timezone.utc) - timedelta(minutes=20)
    assert (
        evaluate_sla_status(severity="P0", owner=None, created_at=created) == "breached"
    )


def test_p1_sla_within_when_assigned() -> None:
    created = datetime.now(timezone.utc) - timedelta(hours=2)
    assert (
        evaluate_sla_status(severity="P1", owner="alice", created_at=created)
        == "within_sla"
    )


def test_p1_sla_at_risk_near_deadline() -> None:
    created = datetime.now(timezone.utc) - timedelta(minutes=50)
    assert (
        evaluate_sla_status(severity="P1", owner=None, created_at=created) == "at_risk"
    )


@pytest.mark.asyncio
async def test_execute_command_version_conflict(monkeypatch) -> None:
    from app.modules.badcases import service as svc

    row = SimpleNamespace(
        badcase_id="bc-1",
        status="OPEN",
        version=3,
        severity="P2",
        category="x",
        type="DATA_QUALITY",
        owner=None,
        capabilities=[],
        privacy_class="INTERNAL_METADATA",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        point_treatment_status="unknown",
        sla_status="within_sla",
        data_completeness="partial",
        reviewer=None,
        redaction_status="NOT_REQUIRED",
        user_visible_status=None,
        root_cause_summary=None,
        reproduction_summary=None,
        closure_evidence={},
        merged_into_badcase_id=None,
    )

    async def _get(*_a, **_k):
        return row

    monkeypatch.setattr(svc._repo, "get", _get)
    monkeypatch.setattr(svc._repo, "get_by_id_any_user", _get)

    with pytest.raises(BadcaseCommandError) as exc:
        await svc.execute_review_command(
            session=SimpleNamespace(),
            badcase_id="bc-1",
            command={
                "action_type": "ADD_NOTE",
                "expected_version": 1,
                "reason": "note",
                "note": "hello",
            },
            actor="tester",
        )
    assert exc.value.code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_execute_command_terminal_state_blocks(monkeypatch) -> None:
    from app.modules.badcases import service as svc

    row = SimpleNamespace(
        badcase_id="bc-closed",
        status="CLOSED",
        version=2,
        severity="P1",
        category="x",
        type="DATA_QUALITY",
        owner="alice",
        capabilities=[],
        privacy_class="INTERNAL_METADATA",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        point_treatment_status="completed",
        sla_status="within_sla",
        data_completeness="complete",
        reviewer="alice",
        redaction_status="PASSED",
        user_visible_status="已解决",
        root_cause_summary="x",
        reproduction_summary="y",
        closure_evidence={},
        merged_into_badcase_id=None,
    )

    async def _get(*_a, **_k):
        return row

    monkeypatch.setattr(svc._repo, "get", _get)
    monkeypatch.setattr(svc._repo, "get_by_id_any_user", _get)

    with pytest.raises(BadcaseCommandError) as exc:
        await svc.execute_review_command(
            session=SimpleNamespace(),
            badcase_id="bc-closed",
            command={
                "action_type": "ADD_NOTE",
                "expected_version": 2,
                "reason": "note",
                "note": "nope",
            },
            actor="tester",
        )
    assert exc.value.code == "TERMINAL_STATE"


@pytest.mark.asyncio
async def test_close_requires_all_evidence(monkeypatch) -> None:
    from app.modules.badcases import service as svc

    row = SimpleNamespace(
        badcase_id="bc-p0",
        status="AWAITING_VALIDATION",
        version=1,
        severity="P0",
        category="leak",
        type="PRIVACY_REDACTION",
        owner="oncall",
        capabilities=[],
        privacy_class="SENSITIVE_USER_CONTENT",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        point_treatment_status="pending",
        sla_status="within_sla",
        data_completeness="partial",
        reviewer="oncall",
        redaction_status="PENDING",
        user_visible_status="审核中",
        root_cause_summary=None,
        reproduction_summary=None,
        closure_evidence={},
        merged_into_badcase_id=None,
    )

    async def _get(*_a, **_k):
        return row

    monkeypatch.setattr(svc._repo, "get", _get)
    monkeypatch.setattr(svc._repo, "get_by_id_any_user", _get)

    with pytest.raises(BadcaseCommandError) as exc:
        await svc.execute_review_command(
            session=SimpleNamespace(),
            badcase_id="bc-p0",
            command={
                "action_type": "CLOSE",
                "expected_version": 1,
                "reason": "done",
                "closure_reason": "fixed",
                "fix_or_policy_version": "v1",
                # missing remaining evidence
            },
            actor="tester",
        )
    assert exc.value.code == "CLOSURE_EVIDENCE_REQUIRED"


@pytest.mark.asyncio
async def test_idempotent_replay_returns_prior(monkeypatch) -> None:
    from app.modules.badcases import service as svc

    prior = SimpleNamespace(
        id=uuid4(),
        badcase_id="bc-1",
        action_type="ADD_NOTE",
        actor="tester",
        actor_role="BADCASE_REVIEWER",
        reason="note",
        from_status="OPEN",
        to_status="OPEN",
        expected_version=1,
        resulting_version=2,
        evidence_refs=[],
        created_at=datetime.now(timezone.utc),
    )
    row = SimpleNamespace(
        badcase_id="bc-1",
        status="OPEN",
        version=2,
        severity="P3",
        category="ux",
        type="PRODUCT_FUNNEL_UX",
        owner=None,
        capabilities=[],
        privacy_class="INTERNAL_METADATA",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        point_treatment_status="not_required",
        sla_status="within_sla",
        data_completeness="partial",
        reviewer=None,
        redaction_status="NOT_REQUIRED",
        user_visible_status=None,
        root_cause_summary=None,
        reproduction_summary=None,
        closure_evidence={},
        merged_into_badcase_id=None,
    )

    async def _find(*_a, **_k):
        return prior

    async def _get(*_a, **_k):
        return row

    monkeypatch.setattr(svc._repo, "find_action_by_idempotency", _find)
    monkeypatch.setattr(svc._repo, "get", _get)
    monkeypatch.setattr(svc._repo, "get_by_id_any_user", _get)

    receipt = await svc.execute_review_command(
        session=SimpleNamespace(),
        badcase_id="bc-1",
        command={
            "action_type": "ADD_NOTE",
            "expected_version": 1,
            "reason": "note",
            "note": "hello",
        },
        actor="tester",
        idempotency_key="idem-abc-12345",
    )
    assert receipt["idempotent_replay"] is True
    assert receipt["audit_event_id"] == str(prior.id)


@pytest.mark.asyncio
async def test_create_recurrence_requires_terminal(monkeypatch) -> None:
    from app.modules.badcases import service as svc

    row = SimpleNamespace(status="OPEN", badcase_id="bc-open")

    async def _get(*_a, **_k):
        return row

    monkeypatch.setattr(svc._repo, "get_by_id_any_user", _get)

    with pytest.raises(BadcaseCommandError) as exc:
        await svc.create_recurrence(
            session=SimpleNamespace(),
            terminal_badcase_id="bc-open",
            user_id=uuid4(),
            reason="recur",
            actor="tester",
        )
    assert exc.value.code == "NOT_TERMINAL"
