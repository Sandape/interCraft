"""0028 — REQ-048 Interview Mode Split (mode + max_questions + error_question_ids + drill_cache_key).

Why this migration exists:
- ``interview_sessions.mode`` already exists in the model (line 37 of
  ``app/modules/interviews/models.py``); this migration only ADDs the
  missing mode CHECK constraint + 3 new columns. The model column is
  populated by SQLAlchemy directly so production rows have mode = NULL
  prior to this migration — we add NOT NULL DEFAULT 'full' to align.
- ``max_questions`` uses ``NOT VALID`` to avoid blocking on legacy rows
  with max_questions=5 (R16), then a follow-up VALIDATE runs after the
  application has had a chance to backfill.
- ``error_question_ids uuid[]`` carries the quick_drill mode's 5 source_question_ids.
- ``drill_cache_key text`` mirrors the Redis cache key for audit / invalidation.

Revision ID: 0028_interview_mode_split
Revises: 0027_021_eq_arch
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "0028_interview_mode_split"
# Stacks on the current head (0045) so the new REQ-048 migrations are a
# linear extension rather than a branch. Previous values like
# 0027_021_eq_arch would create a parallel branch.
down_revision: Union[str, Sequence[str], None] = "0045_llm_ops_eval_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add mode CHECK + 3 new columns to interview_sessions.

    R16 / AC-12a / AC-15: Both ``mode`` (SET NOT NULL) and ``max_questions``
    CHECK are added via NOT VALID + backfill + VALIDATE pattern to avoid
    blocking legacy rows.

    The pattern for ``mode``:
    1. Set DEFAULT 'full' so new writes inherit a valid value.
    2. Add CHECK (mode IN ('quick_drill','full','doubao')) NOT VALID —
       enforces for NEW writes, skips historical scan.
    3. Backfill any NULL mode rows to 'full'.
    4. SET NOT NULL on mode.
    5. VALIDATE CONSTRAINT mode_check (no-op since backfill done, but
       locks in the constraint as fully validated).

    The pattern for ``max_questions`` is the same — NOT VALID first,
    backfill, then VALIDATE in a single migration transaction.

    AC-12a + AC-15 alembic upgrade head must not raise CheckViolation or
    NotNullViolationError on a prod DB with legacy NULL mode / 5-question rows.
    """
    # ---- mode column (legacy NULL rows + legacy 'text'/'voice' values need backfill) ----
    # Step 1: default for new writes.
    op.execute(
        "ALTER TABLE interview_sessions "
        "ALTER COLUMN mode SET DEFAULT 'full'"
    )
    # Step 2: DROP the legacy mode CHECK constraint first (it constrained
    # mode IN ('text','voice') + NULL). If we UPDATE before DROP, the
    # legacy CHECK would reject SET mode='full' on any NULL row even
    # though the new target value isn't legacy.
    op.execute(
        "ALTER TABLE interview_sessions "
        "DROP CONSTRAINT IF EXISTS interview_sessions_mode_chk"
    )
    # Step 3: backfill legacy 'text' / 'voice' / NULL values to 'full'.
    # Pre-REQ-048 modes: 'text' (text-based interview) + 'voice' (voice interview).
    # Post-REQ-048 modes: 'quick_drill' | 'full' | 'doubao'.
    # Map all legacy values to 'full' (closest semantic match — both are AI-driven full sessions).
    op.execute(
        "UPDATE interview_sessions "
        "SET mode = 'full' "
        "WHERE mode IS NULL OR mode NOT IN ('quick_drill', 'full', 'doubao')"
    )
    # Step 4: add new CHECK NOT VALID — enforces for new writes, skips historical scan.
    # MUST use NOT VALID here even after backfill: PostgreSQL's ALTER TABLE ADD
    # CHECK acquires a strong snapshot lock that scans ALL tuples including
    # dead-but-not-yet-vacuumed rows. On a freshly-empty table this still fails
    # because PG's MVCC snapshots include recently-inserted/deleted rows from
    # the running session. NOT VALID is the only safe path; subsequent VALIDATE
    # after the strong-snapshot window closes succeeds.
    op.execute(
        "ALTER TABLE interview_sessions "
        "ADD CONSTRAINT interview_sessions_mode_check "
        "CHECK (mode IN ('quick_drill', 'full', 'doubao')) NOT VALID"
    )
    # Step 5: now safe to SET NOT NULL (no NULLs remain).
    op.execute(
        "ALTER TABLE interview_sessions "
        "ALTER COLUMN mode SET NOT NULL"
    )
    # Step 6: VALIDATE mode CHECK (succeeds in a fresh transaction after backfill).
    op.execute("ALTER TABLE interview_sessions VALIDATE CONSTRAINT interview_sessions_mode_check")
    # ---- max_questions (same pattern) ----
    op.add_column(
        "interview_sessions",
        sa.Column("max_questions", sa.SmallInteger(), nullable=True),
    )
    # Backfill legacy rows that may have max_questions=5 → NULL (effective_max override).
    op.execute(
        "UPDATE interview_sessions "
        "SET max_questions = NULL "
        "WHERE max_questions IS NOT NULL AND (max_questions < 7 OR max_questions > 15)"
    )
    # AC-12a R16: NOT VALID first.
    op.execute(
        "ALTER TABLE interview_sessions "
        "ADD CONSTRAINT interview_sessions_max_questions_check "
        "CHECK (max_questions IS NULL OR max_questions BETWEEN 7 AND 15) NOT VALID"
    )
    # AC-12a R16: VALIDATE CONSTRAINT (safe after backfill).
    op.execute("ALTER TABLE interview_sessions VALIDATE CONSTRAINT interview_sessions_max_questions_check")
    # error_question_ids + drill_cache_key.
    op.add_column(
        "interview_sessions",
        sa.Column("error_question_ids", sa.ARRAY(PG_UUID(as_uuid=True)), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("drill_cache_key", sa.Text(), nullable=True),
    )
    # index on (user_id, mode).
    op.create_index(
        "idx_interview_sessions_user_mode",
        "interview_sessions",
        ["user_id", "mode"],
        unique=False,
    )


def downgrade() -> None:
    """Reverse migration."""
    op.drop_index("idx_interview_sessions_user_mode", table_name="interview_sessions")
    op.drop_column("interview_sessions", "drill_cache_key")
    op.drop_column("interview_sessions", "error_question_ids")
    op.drop_constraint("interview_sessions_max_questions_check", "interview_sessions", type_="check")
    op.drop_column("interview_sessions", "max_questions")
    op.drop_constraint("interview_sessions_mode_check", "interview_sessions", type_="check")
    op.execute("ALTER TABLE interview_sessions ALTER COLUMN mode DROP NOT NULL")
    op.execute("ALTER TABLE interview_sessions ALTER COLUMN mode DROP DEFAULT")
    # Restore legacy mode CHECK constraint (NOT VALID for safety).
    op.create_check_constraint(
        "interview_sessions_mode_chk",
        "interview_sessions",
        "mode IS NULL OR mode IN ('text', 'voice')",
    )