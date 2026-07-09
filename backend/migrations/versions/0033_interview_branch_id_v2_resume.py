"""Allow interview branch_id to reference v2 resumes.

REQ-048 launch flow chooses resumes from the v2 resume center. The existing
interview_sessions.branch_id column is still the public API field, but the
database FK to legacy resume_branches prevents storing a resumes_v2.id.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_interview_branch_v2"
down_revision: Union[str, None] = "0032_051_is_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _branch_fk_names() -> list[str]:
    inspector = sa.inspect(op.get_bind())
    names: list[str] = []
    for fk in inspector.get_foreign_keys("interview_sessions"):
        if fk.get("referred_table") != "resume_branches":
            continue
        if fk.get("constrained_columns") == ["branch_id"] and fk.get("name"):
            names.append(str(fk["name"]))
    return names


def upgrade() -> None:
    for name in _branch_fk_names():
        op.drop_constraint(name, "interview_sessions", type_="foreignkey")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    has_fk = any(
        fk.get("referred_table") == "resume_branches"
        and fk.get("constrained_columns") == ["branch_id"]
        for fk in inspector.get_foreign_keys("interview_sessions")
    )
    if has_fk:
        return

    op.execute(
        """
        UPDATE interview_sessions s
        SET branch_id = NULL
        WHERE branch_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM resume_branches rb WHERE rb.id = s.branch_id
          )
        """
    )
    op.create_foreign_key(
        "interview_sessions_branch_id_fkey",
        "interview_sessions",
        "resume_branches",
        ["branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
