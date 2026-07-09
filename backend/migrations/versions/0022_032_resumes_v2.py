"""Create resumes_v2 + resume_statistics_v2 + resume_analysis_v2 tables
(REQ-032, T010).

The ``resumes_v2`` table is the new authoring + content surface for the
JSON-Schema-based resume renderer. Its siblings carry public-access
counters and an AI-analysis snapshot, respectively. The old v1
``resume_branches`` / ``resume_blocks`` tables are untouched.

Why ``password_hash IS NULL OR is_public = true``?
    Spec data-model.md §8.2: a password MUST only be set when the
    resume is public. CHECK constraint enforces this at the storage
    layer so a forgotten application-layer check can never leave a
    password stranded on a private resume.

Why UNIQUE (user_id, slug) not UNIQUE (slug) globally?
    Slugs are scoped per user: alice/``senior-eng`` and bob/``senior-eng``
    are independent. The partial public lookup index
    (user_id, slug) WHERE is_public supports the public view path
    without scanning the whole table.

Why RLS on ``resumes_v2`` but not on the statistics / analysis rows?
    Statistics and analysis rows are reached only via the parent
    resume's user_id; their FK + ON DELETE CASCADE keeps them
    consistent. Adding RLS would double the WHERE-clause burden for
    no security gain. The parent row's RLS already gates access.

Why a BEFORE UPDATE trigger to bump ``updated_at`` rather than the
SQLAlchemy ``onupdate=func.now()`` default?
    The column already has onupdate wired up at the ORM layer, but
    raw SQL updates (e.g. ``UPDATE resumes_v2 SET version=...``) bypass
    SQLAlchemy. A trigger ensures the timestamp is always bumped,
    keeping the LISTEN/NOTIFY payload accurate.

No new package dependencies.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID

revision = "0022_032_resumes_v2"
down_revision = "0021_a2a_messages"
branch_labels = None
depends_on = None


def _enable_rls(table: str) -> None:
    """Per-user RLS using app.user_id GUC.

    Mirrors the helper in 0020_irt_item_bank.py.
    """
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING (user_id = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);"
    )


def upgrade() -> None:
    # ── resumes_v2 ────────────────────────────────────────────────────────
    op.create_table(
        "resumes_v2",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column(
            "tags",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "slug", name="uq_resumes_v2_user_slug"),
        sa.CheckConstraint(
            "password_hash IS NULL OR is_public = true",
            name="ck_resumes_v2_password_only_when_public",
        ),
        sa.CheckConstraint(
            "version >= 0",
            name="ck_resumes_v2_version_nonneg",
        ),
    )
    op.create_index(
        "idx_resumes_v2_user_updated",
        "resumes_v2",
        ["user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "idx_resumes_v2_public_user_slug",
        "resumes_v2",
        ["user_id", "slug"],
        postgresql_where=sa.text("is_public = true"),
    )

    # BEFORE UPDATE trigger to bump updated_at even for raw SQL updates.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION resumes_v2_bump_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER resumes_v2_set_updated_at
        BEFORE UPDATE ON resumes_v2
        FOR EACH ROW
        EXECUTE FUNCTION resumes_v2_bump_updated_at();
        """
    )

    _enable_rls("resumes_v2")

    # ── resume_statistics_v2 ─────────────────────────────────────────────
    op.create_table(
        "resume_statistics_v2",
        sa.Column("resume_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "downloads",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("resume_id"),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes_v2.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("views >= 0", name="ck_resume_statistics_v2_views_nonneg"),
        sa.CheckConstraint(
            "downloads >= 0", name="ck_resume_statistics_v2_downloads_nonneg"
        ),
    )

    # ── resume_analysis_v2 ───────────────────────────────────────────────
    op.create_table(
        "resume_analysis_v2",
        sa.Column("resume_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("analysis", JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'success'"),
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("resume_id"),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes_v2.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('success','failed')",
            name="ck_resume_analysis_v2_status",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS resumes_v2_set_updated_at ON resumes_v2;")
    op.execute("DROP FUNCTION IF EXISTS resumes_v2_bump_updated_at();")
    op.drop_table("resume_analysis_v2")
    op.drop_table("resume_statistics_v2")
    op.drop_table("resumes_v2")
