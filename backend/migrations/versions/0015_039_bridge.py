"""Stub bridge migration (REQ-039 chain fix). See 0012_039_bridge.py."""
from __future__ import annotations

from alembic import op

revision = "0015_039_bridge"
down_revision = "0014_039_bridge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass