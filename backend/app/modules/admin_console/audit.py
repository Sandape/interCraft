"""REQ-039 B1 — admin_console audit writer.

Thin convenience wrapper around :func:`repository.write_audit` that
also accepts pre-validated action / target_kind tokens. All audit
writes go through this module so the action vocabulary is enforced
in one place (DB CHECK constraint is the second line of defense).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin_console import repository

VALID_ACTIONS: frozenset[str] = frozenset(
    {"replay_triggered", "diff_computed", "tag_added", "tag_removed"}
)
VALID_TARGET_KINDS: frozenset[str] = frozenset({"trace", "task", "diff"})


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


__all__ = [
    "VALID_ACTIONS",
    "VALID_TARGET_KINDS",
    "log_diff",
    "log_replay",
    "log_tag_added",
    "log_tag_removed",
]