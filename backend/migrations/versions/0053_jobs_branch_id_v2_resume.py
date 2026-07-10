"""Allow jobs.branch_id to reference v2 resumes.

REQ-055 derived resumes are stored in resumes_v2, while job interview launch
still uses jobs.branch_id as the public binding field. The old database FK to
resume_branches prevents binding a derived resume, so ownership validation is
handled in JobService and the schema stores the UUID without a single-table FK.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053_jobs_branch_v2"
down_revision: Union[str, None] = "0052_interview_plan_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _branch_fk_names() -> list[str]:
    inspector = sa.inspect(op.get_bind())
    names: list[str] = []
    for fk in inspector.get_foreign_keys("jobs"):
        if fk.get("referred_table") != "resume_branches":
            continue
        if fk.get("constrained_columns") == ["branch_id"] and fk.get("name"):
            names.append(str(fk["name"]))
    return names


def upgrade() -> None:
    for name in _branch_fk_names():
        op.drop_constraint(name, "jobs", type_="foreignkey")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    has_fk = any(
        fk.get("referred_table") == "resume_branches"
        and fk.get("constrained_columns") == ["branch_id"]
        for fk in inspector.get_foreign_keys("jobs")
    )
    if has_fk:
        return

    op.execute(
        """
        UPDATE jobs j
        SET branch_id = NULL
        WHERE branch_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM resume_branches rb WHERE rb.id = j.branch_id
          )
        """
    )
    op.create_foreign_key(
        "jobs_branch_id_fkey",
        "jobs",
        "resume_branches",
        ["branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
