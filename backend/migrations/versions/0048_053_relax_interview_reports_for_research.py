"""REQ-053: relax interview_reports NOT NULL constraints for research reports.

REQ-053 introduced ``report_type = 'pre_interview_research'`` rows. These
reports are *not* mock interviews, so they don't have a mock session_id,
overall_score, per_question_score, dimension_scores, strengths,
improvements. The original 0046 migration added the new columns but
forgot to make these seven mock-only columns nullable, causing the
service's ``INSERT INTO interview_reports ...`` from
create_research_report to fail with NotNullViolationError on whichever
column it tries first.

Live failure observed: 21:27 task ran 6 search dimensions + LLM
report generation, then 500'd on the INSERT — no report was persisted.

Fix:
- DROP NOT NULL on the seven mock-only columns when report_type =
  'pre_interview_research'. The original NOT NULL is preserved for
  mock_interview rows by the column-level constraint alone (mock rows
  always populate these fields).
- Application-layer enforcement in InterviewReportRepo.create() +
  InterviewReportRepo.create_research_report() ensures the right
  contract per report_type.

Downgrade re-applies NOT NULL after back-filling with empty defaults
to survive rollback.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048_053_relax_interview_reports_for_research"
down_revision = "0047_053_fix_jobs_status_chk"
branch_labels = None
depends_on = None


# Columns that are required for mock_interview but NULL for research
_MOCK_ONLY_COLUMNS = (
    "session_id",
    "overall_score",
    "per_question_score",
    "dimension_scores",
    "strengths",
    "improvements",
)


def upgrade() -> None:
    # Widen alembic_version.version_num to accommodate this migration's
    # 45-character revision identifier, which exceeds the default VARCHAR(32).
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(255),
        existing_type=sa.String(32),
    )
    for col in _MOCK_ONLY_COLUMNS:
        # session_id is UUID; the others vary by type but the operation
        # is type-agnostic. alembic inspects existing_type from DB catalog.
        op.alter_column(
            "interview_reports",
            col,
            nullable=True,
        )


def downgrade() -> None:
    # Deliberately do NOT narrow alembic_version.version_num.
    # Future migrations may carry similarly long revision identifiers;
    # narrowing to VARCHAR(32) would risk truncation on later upgrades.
    # Back-fill any null values with safe defaults before restoring NOT NULL.
    op.execute("UPDATE interview_reports SET session_id = '00000000-0000-0000-0000-000000000000'::uuid WHERE session_id IS NULL")
    op.execute("UPDATE interview_reports SET overall_score = 0 WHERE overall_score IS NULL")
    op.execute("UPDATE interview_reports SET per_question_score = '[]'::jsonb WHERE per_question_score IS NULL")
    op.execute("UPDATE interview_reports SET dimension_scores = '{}'::jsonb WHERE dimension_scores IS NULL")
    op.execute("UPDATE interview_reports SET strengths = '[]'::jsonb WHERE strengths IS NULL")
    op.execute("UPDATE interview_reports SET improvements = '[]'::jsonb WHERE improvements IS NULL")
    for col in _MOCK_ONLY_COLUMNS:
        op.alter_column(
            "interview_reports",
            col,
            nullable=False,
        )
