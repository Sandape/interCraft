"""Add error_questions.source_question_id + partial unique index (Feature 019 — Interview→ErrorBook auto link).

Revision ID: 0011_019_error_source_question_id
Revises: 0010_019_interview_job_id
Create Date: 2026-06-17

Note: spec.md / data-model.md originally called for a FK to ``interview_questions.id``.
Phase 4 ships ``interview_reports.per_question_score`` JSONB and ``ai_messages`` instead of
a dedicated ``interview_questions`` table — so the FK is intentionally a *plain UUID* column.
Correlation with the live question is reconstructed at query time via the
``(session_id, checkpoint_id, role='assistant')`` tuple in ``ai_messages``.
"""
from __future__ import annotations

from alembic import op

revision = "0011_error_src_qid"
down_revision = "0010_interview_job_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE error_questions "
        "ADD COLUMN IF NOT EXISTS source_question_id UUID"
    )
    op.create_index(
        "ix_error_questions_source_question_id",
        "error_questions",
        ["source_question_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS error_questions_source_question_id_uidx "
        "ON error_questions (source_question_id) "
        "WHERE source_question_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS error_questions_source_question_id_uidx")
    op.drop_index(
        "ix_error_questions_source_question_id", table_name="error_questions"
    )
    op.execute("ALTER TABLE error_questions DROP COLUMN IF EXISTS source_question_id")
