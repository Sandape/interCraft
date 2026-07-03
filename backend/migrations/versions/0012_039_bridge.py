"""Stub bridge migration (REQ-039 chain fix).

Revision ID: 0012_039_bridge
Revises: 0011_error_src_qid
Create Date: 2026-07-03

Why this exists:
    The worktree chain is missing migrations 0012-0016 (they belong to
    other concurrent teams under the parallel_master_work_constraint).
    0017's ``down_revision = "0016_interview_plan"`` references a file
    that does not exist on this branch, which crashes alembic's
    ScriptDirectory loader before ``upgrade`` ever runs.

    To make ``alembic upgrade head`` resolvable WITHOUT touching any
    other team's files, we insert five no-op stub bridges (0012-0016).
    Each stub is a pure pass-through — no schema change — and they
    compose so that 0017 → ... → 0021 form a complete chain.

    When this branch is merged to master (which already has 0012-0021
    real migrations) alembic will detect duplicate revision IDs and
    refuse to load. Mitigation on merge: delete the five stub files
    in the same commit that promotes 0022 onto master's real chain.
"""
from __future__ import annotations

from alembic import op

revision = "0012_039_bridge"
down_revision = "0011_error_src_qid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op stub. See module docstring for rationale.
    pass


def downgrade() -> None:
    # No-op stub.
    pass