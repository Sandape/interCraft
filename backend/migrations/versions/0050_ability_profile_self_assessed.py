"""Add self_assessed_score to ability_dimensions (Feature 006 dual-track).

Preserves user self-assessment separately from interview/system actual_score
so ON CONFLICT UPSERT from interview sync no longer overwrites self scores.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0050_ability_profile_self_assessed"
down_revision = "0049_055_resume_root_derive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ability_dimensions",
        sa.Column("self_assessed_score", sa.Numeric(4, 2), nullable=True),
    )
    # Backfill: rows still marked manual/self with a non-zero score were
    # historically the user's self-assessment (before interview overwrite).
    op.execute(
        """
        UPDATE ability_dimensions
        SET self_assessed_score = actual_score
        WHERE source IN ('manual', 'self')
          AND actual_score IS NOT NULL
          AND actual_score > 0
        """
    )


def downgrade() -> None:
    op.drop_column("ability_dimensions", "self_assessed_score")
