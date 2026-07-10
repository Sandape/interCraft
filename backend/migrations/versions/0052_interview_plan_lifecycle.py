"""0052 — plan lifecycle columns on interview_sessions (REQ-058).

Adds explicit plan_status / error / degraded fields so Live and WS can
read stable lifecycle without re-inferring from interview_plan JSON.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0052_interview_plan_lifecycle"
down_revision = "0051_interview_use_variants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("plan_status", sa.Text(), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("plan_error_code", sa.Text(), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("plan_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column(
            "degraded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "degraded")
    op.drop_column("interview_sessions", "plan_error_message")
    op.drop_column("interview_sessions", "plan_error_code")
    op.drop_column("interview_sessions", "plan_status")
