"""0051 — persist use_variants on interview_sessions (REQ-048 US5).

The create API already accepts ``use_variants`` for quick_drill, but the
column was never added so the flag could not survive past the first
graph seed / resume. Default false matches AC-25 (verbatim replay).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0051_interview_use_variants"
down_revision = "0050_ability_profile_self_assessed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column(
            "use_variants",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "use_variants")
