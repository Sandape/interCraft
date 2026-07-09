"""REQ-053 fix: replace jobs.status CHECK constraint with the new 7-state model.

The original constraint (defined in 0002_phase2_entities) used the legacy
status values ('oa','hr','offer','rejected','withdrawn'). REQ-053 US1
migrates the application to a new 7-state model
('applied','test','interview_1','interview_2','interview_3','failed','passed'),
but 0046_053_interview_research did not update this CHECK constraint.

This migration:
1. Drops the old constraint `jobs_status_chk`
2. Creates a new constraint `jobs_status_chk` with the REQ-053 state set

Safe to run after 0046 has applied (the status data migration is handled by
the application-level `jobs.cli migrate-status` command, not by DDL).
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0047_053_fix_jobs_status_chk"
down_revision = "d39a0181498c"  # merge_052_053
branch_labels = None
depends_on = None


_NEW_STATUS_SET = (
    "'applied','test','interview_1','interview_2','interview_3','failed','passed'"
)


def upgrade() -> None:
    # IF EXISTS so this migration is idempotent if the old constraint was
    # already dropped by an out-of-band fix script.
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_status_chk")
    op.create_check_constraint(
        "jobs_status_chk",
        "jobs",
        f"status IN ({_NEW_STATUS_SET})",
    )


def downgrade() -> None:
    op.drop_constraint("jobs_status_chk", "jobs", type_="check")
    op.create_check_constraint(
        "jobs_status_chk",
        "jobs",
        "status IN ('applied','test','oa','hr','offer','rejected','withdrawn')",
    )


__all__ = ["upgrade", "downgrade"]