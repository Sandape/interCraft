"""REQ-039 B1 — admin_console audit writer (US1 + US4 extended).

Thin convenience wrapper around :func:`repository.write_audit` that
also accepts pre-validated action / target_kind tokens. All audit
writes go through this module so the action vocabulary is enforced
in one place (DB CHECK constraint is the second line of defense).

Action vocabulary (locked across US1 + US4):

- US1 baseline (4): ``replay_triggered`` / ``diff_computed`` /
  ``tag_added`` / ``tag_removed``.
- US4 additions (4): ``incident_status_changed`` /
  ``incident_comment_added`` / ``badcase_status_changed`` /
  ``badcase_escalated``.

Target kinds (US4 additions): ``incident`` / ``badcase``.

[NOTE] The DB CHECK constraint in migration 0022 currently only
recognizes the 4 US1 actions. Phase 2 batch 4 will widen the CHECK
constraint to include the 4 US4 actions. For US4 we ONLY add the
Python-side tokens so the call sites can be wired and unit-tested
without touching the DB. The write_audit helper is no-op for the
new actions until the migration lands — see :func:`log_incident_change`
+ :func:`log_badcase_change` for the explicit comment.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin_console import repository

#: US1 baseline 4 actions (DB-backed) + US4 4 actions (Python-side
#: until migration 0022 widens the CHECK constraint in Phase 2 batch 4).
VALID_ACTIONS: frozenset[str] = frozenset(
    {
        "replay_triggered",
        "diff_computed",
        "tag_added",
        "tag_removed",
        "incident_status_changed",
        "incident_comment_added",
        "badcase_status_changed",
        "badcase_escalated",
    }
)
VALID_TARGET_KINDS: frozenset[str] = frozenset(
    {"trace", "task", "diff", "incident", "badcase"}
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
# US4 — incident / badcase audit helpers
#
# [CROSS-TEAM-DEBT] Phase 2 batch 4 will widen the ``admin_audit_log``
# CHECK constraint to include the 4 US4 actions. Until then these
# helpers use :func:`_write_audit_unsafe` which is gated by a
# Python-side allowlist. Tests use the ``admin_console.incidents.service``
# in-memory audit buffer for end-to-end coverage.
# ---------------------------------------------------------------------------


#: Subset of actions that are NOT yet DB-persisted (Phase 2 batch 4
#: will widen the migration 0022 CHECK constraint to include them).
_DB_BLOCKED_ACTIONS: frozenset[str] = frozenset(
    {
        "incident_status_changed",
        "incident_comment_added",
        "badcase_status_changed",
        "badcase_escalated",
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
    "log_incident_change",
    "log_incident_comment",
    "log_replay",
    "log_tag_added",
    "log_tag_removed",
]
