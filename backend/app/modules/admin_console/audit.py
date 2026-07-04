"""REQ-039 B1 — admin_console audit writer (US1 + US4 + US6 extended).

Thin convenience wrapper around :func:`repository.write_audit` that
also accepts pre-validated action / target_kind tokens. All audit
writes go through this module so the action vocabulary is enforced
in one place (DB CHECK constraint is the second line of defense).

Action vocabulary (locked across US1 + US4 + US6 + US7 + CROSS):

- US1 baseline (4): ``replay_triggered`` / ``diff_computed`` /
  ``tag_added`` / ``tag_removed``.
- US4 additions (4): ``incident_status_changed`` /
  ``incident_comment_added`` / ``badcase_status_changed`` /
  ``badcase_escalated``.
- US6 additions (3): ``sensitive_reveal`` / ``export`` /
  ``review_snapshot``.
- US7: reuses ``review_snapshot`` action (target_kind='snapshot');
  no new action tokens are introduced. The taxonomy stays at
  11 actions (per AC-34.1).
- CROSS (FR-006 saved views) adds the 12th action
  ``saved_view_change`` (target_kind='saved_view') for create /
  update / delete lifecycle events. This unlocks SC-009 auditing
  for FR-006 saved views (AC-6.7).

Target kinds:
- US1 (3): ``trace`` / ``task`` / ``diff``.
- US4 (2): ``incident`` / ``badcase``.
- US6 (8): ``user_resume`` / ``user_interview`` / ``ai_prompt`` /
  ``ai_model_output`` / ``incident_payload`` / ``export`` /
  ``snapshot`` / ``governance``.

[NOTE] The DB CHECK constraint in migration 0022 currently only
recognizes the 4 US1 actions. Phase 2 batch 5 will widen the CHECK
constraint to include the 4 US4 + 3 US6 actions. For US4 + US6 we
ONLY add the Python-side tokens so the call sites can be wired and
unit-tested without touching the DB. The write_audit helper is
no-op for the new actions until the migration lands — see
:func:`log_incident_change` + :func:`log_badcase_change` +
:func:`log_sensitive_reveal` + :func:`log_export` +
:func:`log_governance_change` for the explicit comment.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin_console import repository

#: US1 baseline 4 actions (DB-backed) + US4 4 + US6 3 + CROSS 1 = 12 total
#: (Python-side until migration 0022 widens the CHECK constraint in
#: Phase 2 batch 5).
VALID_ACTIONS: frozenset[str] = frozenset(
    {
        # US1 (4)
        "replay_triggered",
        "diff_computed",
        "tag_added",
        "tag_removed",
        # US4 (4)
        "incident_status_changed",
        "incident_comment_added",
        "badcase_status_changed",
        "badcase_escalated",
        # US6 (3)
        "sensitive_reveal",
        "export",
        "review_snapshot",
        # CROSS FR-006 (1) — saved view lifecycle (create/update/delete)
        "saved_view_change",
    }
)
VALID_TARGET_KINDS: frozenset[str] = frozenset(
    {
        # US1
        "trace",
        "task",
        "diff",
        # US4
        "incident",
        "badcase",
        # US6
        "user_resume",
        "user_interview",
        "ai_prompt",
        "ai_model_output",
        "incident_payload",
        "export",
        "snapshot",
        "governance",
        # CROSS FR-006 — saved view target kind
        "saved_view",
    }
)


async def log_replay(
    session: AsyncSession,
    user_id: UUID,
    *,
    orig_trace_id: UUID,
    new_trace_id: UUID,
) -> None:
    """Audit a Replay trigger (FR-008 / IC-5)."""
    await repository.write_audit(
        session,
        user_id=user_id,
        action="replay_triggered",
        target_kind="trace",
        target_id=orig_trace_id,
        details={
            "orig_trace_id": str(orig_trace_id),
            "new_trace_id": str(new_trace_id),
        },
    )


async def log_diff(
    session: AsyncSession,
    user_id: UUID,
    *,
    left_trace_id: UUID,
    right_trace_id: UUID,
    node_count: int,
) -> None:
    """Audit a Diff call (FR-014 / IC-5)."""
    await repository.write_audit(
        session,
        user_id=user_id,
        action="diff_computed",
        target_kind="diff",
        target_id=None,
        details={
            "left_trace_id": str(left_trace_id),
            "right_trace_id": str(right_trace_id),
            "node_count": node_count,
        },
    )


async def log_tag_added(
    session: AsyncSession,
    user_id: UUID,
    *,
    task_id: UUID,
    tag: str,
) -> None:
    """Audit a tag add (FR-020 / FR-030)."""
    await repository.write_audit(
        session,
        user_id=user_id,
        action="tag_added",
        target_kind="task",
        target_id=task_id,
        details={"tag": tag},
    )


async def log_tag_removed(
    session: AsyncSession,
    user_id: UUID,
    *,
    task_id: UUID,
    tag: str,
) -> None:
    """Audit a tag remove (FR-020 / FR-030)."""
    await repository.write_audit(
        session,
        user_id=user_id,
        action="tag_removed",
        target_kind="task",
        target_id=task_id,
        details={"tag": tag},
    )


# ---------------------------------------------------------------------------
# US4 + US6 — incident / badcase / sensitive / export / governance
# audit helpers
#
# [CROSS-TEAM-DEBT] Phase 2 batch 5 will widen the ``admin_audit_log``
# CHECK constraint to include the 4 US4 + 3 US6 actions. Until then
# these helpers use :func:`_write_audit_unsafe` which is gated by a
# Python-side allowlist. Tests use the ``admin_console.governance.repository``
# in-memory audit buffer for end-to-end coverage.
# ---------------------------------------------------------------------------


#: Subset of actions that are NOT yet DB-persisted (Phase 2 batch 5
#: will widen the migration 0022 CHECK constraint to include them).
_DB_BLOCKED_ACTIONS: frozenset[str] = frozenset(
    {
        # US4
        "incident_status_changed",
        "incident_comment_added",
        "badcase_status_changed",
        "badcase_escalated",
        # US6
        "sensitive_reveal",
        "export",
        "review_snapshot",
        # CROSS FR-006 (Python-side until Phase 2 batch 5 widens CHECK)
        "saved_view_change",
    }
)


async def _write_audit_unsafe(
    session: AsyncSession,
    user_id: UUID,
    action: str,
    target_kind: str,
    target_id: UUID | str | None,
    details: dict[str, Any],
) -> None:
    """Write an audit row, silently skipping DB-blocked US4 actions.

    The 4 US4 actions are gated by the :data:`_DB_BLOCKED_ACTIONS`
    frozenset; when the action is blocked, the call is a no-op. The
    in-memory audit buffer in :mod:`admin_console.incidents.service`
    remains the source of truth for US4 EC-4 verification.
    """
    if action in _DB_BLOCKED_ACTIONS:
        # Phase 1: do not write to the DB — the in-memory buffer in
        # ``incidents.service`` is the verifiable surface (see
        # ``change_incident_status`` + ``get_incident_audit_trail``).
        return
    await repository.write_audit(
        session,
        user_id=user_id,
        action=action,
        target_kind=target_kind,
        target_id=target_id if isinstance(target_id, UUID) or target_id is None else None,
        details=details,
    )


async def log_incident_change(
    session: AsyncSession,
    user_id: UUID,
    *,
    incident_id: str,
    actor: str,
    reason: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> None:
    """Audit an incident status change (EC-4 / FR-022).

    See :data:`_DB_BLOCKED_ACTIONS` for the Phase 2 batch 4 caveat.
    """
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="incident_status_changed",
        target_kind="incident",
        target_id=None,
        details={
            "incident_id": incident_id,
            "actor": actor,
            "reason": reason,
            "before_state": before_state,
            "after_state": after_state,
        },
    )


async def log_incident_comment(
    session: AsyncSession,
    user_id: UUID,
    *,
    incident_id: str,
    comment_id: str,
    actor: str,
    reason: str | None,
) -> None:
    """Audit an incident comment add (FR-022)."""
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="incident_comment_added",
        target_kind="incident",
        target_id=None,
        details={
            "incident_id": incident_id,
            "comment_id": comment_id,
            "actor": actor,
            "reason": reason,
        },
    )


async def log_badcase_change(
    session: AsyncSession,
    user_id: UUID,
    *,
    badcase_id: str,
    actor: str,
    reason: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> None:
    """Audit a badcase status change (EC-4 / FR-023)."""
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="badcase_status_changed",
        target_kind="badcase",
        target_id=None,
        details={
            "badcase_id": badcase_id,
            "actor": actor,
            "reason": reason,
            "before_state": before_state,
            "after_state": after_state,
        },
    )


async def log_badcase_escalate(
    session: AsyncSession,
    user_id: UUID,
    *,
    badcase_id: str,
    incident_id: str,
    actor: str,
) -> None:
    """Audit a badcase escalation to incident (FR-023 / AC-23.4)."""
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="badcase_escalated",
        target_kind="badcase",
        target_id=None,
        details={
            "badcase_id": badcase_id,
            "incident_id": incident_id,
            "actor": actor,
        },
    )


__all__ = [
    "VALID_ACTIONS",
    "VALID_TARGET_KINDS",
    "log_badcase_change",
    "log_badcase_escalate",
    "log_diff",
    "log_export",
    "log_governance_change",
    "log_incident_change",
    "log_incident_comment",
    "log_replay",
    "log_saved_view_change",
    "log_sensitive_reveal",
    "log_snapshot_generated",
    "log_tag_added",
    "log_tag_removed",
]

# ---------------------------------------------------------------------------
# US6 — sensitive reveal / export / governance audit helpers
# (FR-033 + FR-034 + FR-035 + FR-036 + EC-4 self-audit)
# ---------------------------------------------------------------------------


async def log_sensitive_reveal(
    session: AsyncSession,
    user_id: UUID,
    *,
    target_kind: str,
    target_id: str,
    actor: str,
    reason: str,
    result: str,
    visibility_mode: str,
) -> None:
    """Audit a sensitive reveal request (FR-033 + FR-034 AC-34.4).

    See :data:`_DB_BLOCKED_ACTIONS` for the Phase 2 batch 5 caveat.
    """
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="sensitive_reveal",
        target_kind=target_kind,
        target_id=None,
        details={
            "target_kind": target_kind,
            "target_id": target_id,
            "actor": actor,
            "reason": reason,
            "result": result,
            "visibility_mode": visibility_mode,
        },
    )


async def log_export(
    session: AsyncSession,
    user_id: UUID,
    *,
    export_id: str,
    workspace: str,
    format: str,
    actor: str,
    fields_included: list[str],
    fields_redacted: list[str],
    result: str = "executed",
) -> None:
    """Audit an export operation (FR-034 + FR-035 AC-35.5)."""
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="export",
        target_kind="export",
        target_id=None,
        details={
            "export_id": export_id,
            "workspace": workspace,
            "format": format,
            "actor": actor,
            "fields_included": fields_included,
            "fields_redacted": fields_redacted,
            "result": result,
        },
    )


async def log_governance_change(
    session: AsyncSession,
    user_id: UUID,
    *,
    workspace_field: str,
    retention_days: int,
    action: str,
    actor: str,
) -> None:
    """Audit a governance setting change (FR-034 + EC-4 self-audit).

    Maps to the 11th ``review_snapshot`` action with ``target_kind=
    'governance'`` so the audit-event taxonomy stays at 11 tokens
    (per AC-34.1: 11 actions cumulative across US1+US4+US6).
    """
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="review_snapshot",
        target_kind="governance",
        target_id=None,
        details={
            "workspace_field": workspace_field,
            "retention_days": retention_days,
            "action": action,
            "actor": actor,
        },
    )


# ---------------------------------------------------------------------------
# US7 — review snapshot generation audit helper
# (FR-029 + FR-034 + AC-29.2 + EC-3)
# ---------------------------------------------------------------------------


async def log_snapshot_generated(
    session: AsyncSession,
    user_id: UUID,
    *,
    snapshot_id: str,
    workspace: str,
    format: str,
    comparison_period: str,
    actor: str,
    result: str = "executed",
) -> None:
    """Audit a review snapshot generation (FR-029 + FR-034 AC-29.2).

    Maps to the ``review_snapshot`` action (already in US6 + US7
    taxonomy) with ``target_kind='snapshot'``. The DB CHECK constraint
    does not yet accept the US6/US7 actions — see
    :data:`_DB_BLOCKED_ACTIONS`. Real DB persistence lands in
    Phase 2 batch 5.
    """
    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="review_snapshot",
        target_kind="snapshot",
        target_id=None,
        details={
            "snapshot_id": snapshot_id,
            "workspace": workspace,
            "format": format,
            "comparison_period": comparison_period,
            "actor": actor,
            "result": result,
        },
    )


# ---------------------------------------------------------------------------
# CROSS FR-006 — saved view change audit helper
# (FR-006 + FR-034 AC-6.7 + SC-009). 12th audit action.
# ---------------------------------------------------------------------------


async def log_saved_view_change(
    session: AsyncSession,
    user_id: UUID,
    *,
    saved_view_id: str,
    workspace_id: str,
    lifecycle: str,  # 'created' | 'updated' | 'deleted'
    actor: str,
    name: str | None = None,
    shared_with: list[str] | None = None,
    reason: str | None = None,
    result: str = "executed",
) -> None:
    """Audit a saved view change (FR-006 + FR-034 AC-6.7).

    Maps to the 12th audit action ``saved_view_change`` with
    ``target_kind='saved_view'``. The DB CHECK constraint does not
    yet accept this action — see :data:`_DB_BLOCKED_ACTIONS`. Real
    DB persistence lands in Phase 2 batch 5.

    Lifecycle must be one of ``created`` / ``updated`` / ``deleted``
    (raised as ``ValueError`` otherwise).
    """
    if lifecycle not in {"created", "updated", "deleted"}:
        raise ValueError(
            f"saved_view lifecycle must be one of created|updated|deleted, "
            f"got {lifecycle!r}"
        )

    await _write_audit_unsafe(
        session,
        user_id=user_id,
        action="saved_view_change",
        target_kind="saved_view",
        target_id=None,
        details={
            "saved_view_id": saved_view_id,
            "workspace_id": workspace_id,
            "lifecycle": lifecycle,
            "actor": actor,
            "name": name,
            "shared_with": list(shared_with or []),
            "reason": reason,
            "result": result,
        },
    )
