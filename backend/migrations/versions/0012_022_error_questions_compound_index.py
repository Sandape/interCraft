"""Add compound partial index on error_questions for ErrorBook listing perf (Feature 022).

Creates ``idx_error_questions_user_status_freq_created`` on
``(user_id, status, frequency, created_at) WHERE deleted_at IS NULL``.

Revision ID: 0012_error_questions_compound_index
Revises: 0011_error_src_qid
Create Date: 2026-06-22
"""
from __future__ import annotations

from alembic import op

revision = "0012_error_questions_idx"
down_revision = "0011_error_src_qid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_error_questions_user_status_freq_created",
        "error_questions",
        ["user_id", "status", "frequency", "created_at"],
        postgresql_where="deleted_at IS NULL",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_error_questions_user_status_freq_created",
        table_name="error_questions",
        if_exists=True,
    )
