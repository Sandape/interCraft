"""Add is_admin column to users table (REQ-051 FR-001).

- Adds ``is_admin BOOLEAN NOT NULL DEFAULT FALSE`` to ``users``.
- Migrates all existing users: ``subscription = 'pro'`` (FR-002).
- Sets ``demo@intercraft.io`` user ``is_admin = TRUE`` (FR-003).
- Migration is idempotent (safe to re-run on partially-applied state).

Revision ID: 0032_051_is_admin
Revises: 0031_drop_device_unique
Create Date: 2026-07-07
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032_051_is_admin"
down_revision: Union[str, None] = "0031_drop_device_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]

    # FR-001: Add is_admin column (idempotent — skip if already exists).
    if "is_admin" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
        )

    # FR-002: All existing users → subscription = 'pro' (idempotent).
    conn.execute(
        sa.text("UPDATE users SET subscription = 'pro' WHERE subscription != 'pro'")
    )

    # FR-003: demo@intercraft.io → is_admin = TRUE (idempotent).
    conn.execute(
        sa.text(
            "UPDATE users SET is_admin = TRUE WHERE email = 'demo@intercraft.io' AND is_admin IS DISTINCT FROM TRUE"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]

    if "is_admin" in columns:
        op.drop_column("users", "is_admin")
