"""Stub bridge migration (REQ-039 chain fix). See 0012_039_bridge.py.

NOTE: This stub's ``revision`` ID is intentionally set to
``"0016_interview_plan"`` (NOT ``0016_039_bridge``) because 0017's
``down_revision`` references that exact string. Reusing the ID here
makes alembic's revision_map resolve 0017's parent without touching
the 0017 file (which belongs to another team).
"""
from __future__ import annotations

from alembic import op

revision = "0016_interview_plan"
down_revision = "0015_039_bridge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass