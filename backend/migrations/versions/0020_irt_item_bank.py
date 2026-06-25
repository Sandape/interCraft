"""Create IRT item bank tables (REQ-030 US1).

Revision ID: 0020_irt_item_bank
Revises: 0019_resume_avatar
Create Date: 2026-06-25

US1 scope: item bank + responses + thetas tables, plus RLS on user-scoped
tables. The `irt_items` table is intentionally NOT RLS-scoped — it is a
global psychometric resource shared across all users. Per-user RLS
isolation is enforced on `irt_item_responses` and `irt_ability_thetas`,
which carry per-user data that must never leak across users.

Why SET NULL on item_id (not CASCADE)?
    Spec FR-015: "System MUST support item retirement without deleting
    historical response data." CASCADE would erase response history
    when an item is retired; SET NULL preserves the row for audit and
    future drift detection.

No new package dependencies.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_irt_item_bank"
down_revision = "0019_resume_avatar"
branch_labels = None
depends_on = None


def _enable_rls(table: str, policy_column: str = "user_id") -> None:
    """Mirror migrations/versions/0001_initial.py::_enable_rls.

    Per-user RLS: USING + WITH CHECK both compare `policy_column` against
    the `app.user_id` GUC. The caller is responsible for setting the GUC
    inside the transaction that issues the query.
    """
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING ({policy_column} = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK ({policy_column} = current_setting('app.user_id', true)::uuid);"
    )


def upgrade() -> None:
    # ── irt_items (GLOBAL, no RLS) ──────────────────────────────────────────
    op.create_table(
        "irt_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("question_text_hash", sa.Text(), nullable=False),
        sa.Column("difficulty_b", sa.Numeric(6, 3), nullable=False),
        sa.Column("discrimination_a", sa.Numeric(6, 3), nullable=False),
        sa.Column(
            "model",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'2pl'"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'uncalibrated'"),
        ),
        sa.Column(
            "response_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "standard_error",
            sa.Numeric(6, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('uncalibrated','calibrated','retired','flagged')",
            name="ck_irt_items_status",
        ),
        sa.CheckConstraint(
            "model IN ('2pl','3pl')",
            name="ck_irt_items_model",
        ),
        sa.CheckConstraint(
            "difficulty_b BETWEEN -6 AND 6",
            name="ck_irt_items_difficulty_range",
        ),
        sa.CheckConstraint(
            "discrimination_a >= 0 AND discrimination_a <= 5",
            name="ck_irt_items_discrimination_range",
        ),
        sa.CheckConstraint(
            "response_count >= 0",
            name="ck_irt_items_response_count",
        ),
        sa.CheckConstraint(
            "standard_error >= 0",
            name="ck_irt_items_se",
        ),
    )
    # Partial unique index: a non-retired item is unique by
    # (dimension, question_text_hash). Retired items are excluded so
    # the same question can be re-introduced after retirement.
    op.create_index(
        "uq_irt_items_active_dim_hash",
        "irt_items",
        ["dimension", "question_text_hash"],
        unique=True,
        postgresql_where=sa.text("status != 'retired'"),
    )
    op.create_index(
        "idx_irt_items_dimension_status",
        "irt_items",
        ["dimension", "status"],
    )

    # ── irt_item_responses (USER-SCOPED, RLS) ──────────────────────────────
    op.create_table(
        "irt_item_responses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(4, 2), nullable=False),
        sa.Column("source_interview_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["item_id"], ["irt_items.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "response IN ('correct','incorrect')",
            name="ck_irt_responses_label",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 10",
            name="ck_irt_responses_score_range",
        ),
    )
    op.create_index(
        "idx_irt_responses_user_id", "irt_item_responses", ["user_id"]
    )
    op.create_index(
        "idx_irt_responses_user_dim",
        "irt_item_responses",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_irt_responses_item_id", "irt_item_responses", ["item_id"]
    )
    _enable_rls("irt_item_responses")

    # ── irt_ability_thetas (USER-SCOPED, RLS) ──────────────────────────────
    op.create_table(
        "irt_ability_thetas",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("theta", sa.Numeric(6, 3), nullable=False),
        sa.Column("standard_error", sa.Numeric(6, 3), nullable=False),
        sa.Column("n_items", sa.Integer(), nullable=False),
        sa.Column("source_interview_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "model",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'2pl'"),
        ),
        sa.Column(
            "converged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "model IN ('2pl','3pl')",
            name="ck_irt_thetas_model",
        ),
        sa.CheckConstraint(
            "theta BETWEEN -6 AND 6",
            name="ck_irt_thetas_theta_range",
        ),
        sa.CheckConstraint(
            "standard_error > 0",
            name="ck_irt_thetas_se_positive",
        ),
        sa.CheckConstraint(
            "n_items >= 1",
            name="ck_irt_thetas_n_items",
        ),
    )
    op.create_index(
        "idx_irt_thetas_user_id", "irt_ability_thetas", ["user_id"]
    )
    op.create_index(
        "idx_irt_thetas_user_dim",
        "irt_ability_thetas",
        ["user_id", "dimension", "created_at"],
    )
    _enable_rls("irt_ability_thetas")


def downgrade() -> None:
    op.drop_table("irt_ability_thetas")
    op.drop_table("irt_item_responses")
    op.drop_table("irt_items")
