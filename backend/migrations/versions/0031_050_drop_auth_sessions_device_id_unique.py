"""Drop UNIQUE(user_id, device_id) on auth_sessions (FR-001).

Multi-tab coexistence requires that multiple sessions can share the same
(user_id, device_id). The PK (id) is already unique; the device_id column
is informational only and no longer needs uniqueness.

Revision ID: 0031_drop_device_unique
Revises: 0030_analytics_events
Create Date: 2026-07-07
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031_drop_device_unique"
down_revision: Union[str, None] = "0030_analytics_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    constraints = {
        item["name"]
        for item in sa.inspect(bind).get_unique_constraints("auth_sessions")
    }
    if "auth_sessions_device_id_unique" in constraints:
        op.drop_constraint(
            "auth_sessions_device_id_unique",
            "auth_sessions",
            type_="unique",
        )


def downgrade() -> None:
    op.create_unique_constraint(
        "auth_sessions_device_id_unique",
        "auth_sessions",
        ["user_id", "device_id"],
    )
