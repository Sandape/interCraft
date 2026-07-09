"""021 re-add error_questions archived_at column.

Revision ID: 0027_021_eq_arch
Revises: 0022_039_log_center
Create Date: 2026-07-03 21:52:41.810048

Why this migration exists:
- 0014_024_drop_error_questions_archived_at (REQ-024 US4) dropped
  the ``archived_at`` column from ``error_questions``.
- REQ-021/022 models + tests still reference ``archived_at`` for
  the soft-archive flow. Schema drift caused 19 test failures
  (F2 cluster: test_error_coach_idle_reconnect, test_error_coach,
  test_error_questions_crud).
- This migration restores the column to align schema with the
  active SQLAlchemy model and the test suite.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027_021_eq_arch"
down_revision: Union[str, Sequence[str], None] = "0022_039_log_center"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Re-add archived_at column to error_questions."""
    op.add_column(
        "error_questions",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop archived_at column (mirror of 0014 migration)."""
    op.drop_column("error_questions", "archived_at")
