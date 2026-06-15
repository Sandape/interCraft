"""Initial migration — 6 tables + RLS policies.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-12

NOTE: this migration is hand-written. It creates the schema described in
`specs/001-intercraft-product-spec/data-model.md` and enables RLS on every
tenant-scoped table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _enable_rls(table: str, policy_column: str = "user_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING ({policy_column} = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK ({policy_column} = current_setting('app.user_id', true)::uuid);"
    )


def _enable_users_rls() -> None:
    """RLS on `users` is a special case: login must lookup user by email
    before any session is bound. We allow SELECT/INSERT when `app.user_id`
    is unset, and enforce per-row isolation once it is bound.

    NOTES:
    - `current_setting('app.user_id', true)` returns NULL when unset, so we
      `COALESCE` to '' to test "unset".
    - We use `NULLIF` to guard the `::uuid` cast — Postgres may evaluate both
      sides of an OR before applying short-circuit, and an empty string cast
      to uuid raises `invalid input syntax for type uuid: ""`.
    """
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY users_user_isolation ON users "
        "USING ("
        "  COALESCE(current_setting('app.user_id', true), '') = '' "
        "  OR id = NULLIF(current_setting('app.user_id', true), '')::uuid"
        ") "
        "WITH CHECK ("
        "  COALESCE(current_setting('app.user_id', true), '') = '' "
        "  OR id = NULLIF(current_setting('app.user_id', true), '')::uuid"
        ");"
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_sha256", postgresql.BYTEA(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("phone_sha256", postgresql.BYTEA(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("target_role", sa.Text(), nullable=True),
        sa.Column("llm_provider_pref", postgresql.JSONB(), nullable=True),
        sa.Column("subscription", sa.Text(), nullable=False, server_default="free"),
        sa.Column("monthly_token_quota", sa.Integer(), nullable=False, server_default="100000"),
        sa.Column("monthly_token_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_reset_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("allow_concurrent_sessions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="users_email_unique"),
        sa.UniqueConstraint("email_sha256", name="users_email_sha256_unique"),
        sa.UniqueConstraint("phone_sha256", name="users_phone_sha256_unique"),
        sa.CheckConstraint(
            "status IN ('active','soft_deleted','purged','frozen')",
            name="users_status_chk",
        ),
        sa.CheckConstraint(
            "subscription IN ('free','pro','enterprise')",
            name="users_subscription_chk",
        ),
        sa.CheckConstraint(
            "years_of_experience IS NULL OR (years_of_experience >= 0 AND years_of_experience <= 50)",
            name="users_yoe_chk",
        ),
    )
    op.create_index("users_status_deleted_at_idx", "users", ["status", "deleted_at"])
    _enable_users_rls()

    # ---- user_credentials ----
    op.create_table(
        "user_credentials",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("id_card_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("real_name_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("salary_range_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _enable_rls("user_credentials")

    # ---- auth_sessions ----
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("device_name", sa.Text(), nullable=True),
        sa.Column("device_fingerprint", sa.Text(), nullable=False),
        sa.Column("last_seen_ip", postgresql.INET(), nullable=True),
        sa.Column("last_seen_ua", sa.Text(), nullable=True),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("trusted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(device_id) = 64", name="auth_sessions_device_id_chk"),
        sa.CheckConstraint("length(refresh_token_hash) = 64", name="auth_sessions_refresh_hash_chk"),
    )
    op.create_index("auth_sessions_user_last_seen_idx", "auth_sessions", ["user_id", "last_seen_at"])
    op.create_index("auth_sessions_refresh_hash_idx", "auth_sessions", ["refresh_token_hash"])
    # Partial unique on device_id — only enforced for live (non-soft-deleted) sessions
    # so re-login after eviction or rotation can insert a fresh row for the same device.
    op.execute(
        "CREATE UNIQUE INDEX auth_sessions_device_id_unique "
        "ON auth_sessions (device_id) WHERE deleted_at IS NULL;"
    )
    _enable_rls("auth_sessions")

    # ---- resume_branches ----
    op.create_table(
        "resume_branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resume_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "is_main = FALSE OR parent_id IS NULL",
            name="resume_branches_main_no_parent_chk",
        ),
        sa.CheckConstraint(
            "status IN ('draft','optimizing','ready','submitted','archived')",
            name="resume_branches_status_chk",
        ),
        sa.CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 100)",
            name="resume_branches_match_score_chk",
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX resume_branches_user_main_unique "
        "ON resume_branches (user_id) WHERE is_main = TRUE;"
    )
    op.create_index(
        "resume_branches_user_pinned_main_edited_idx",
        "resume_branches",
        ["user_id", "is_pinned", "is_main", "last_edited_at"],
    )
    op.create_index("resume_branches_user_deleted_idx", "resume_branches", ["user_id", "deleted_at"])
    op.create_index("resume_branches_parent_idx", "resume_branches", ["parent_id"])
    _enable_rls("resume_branches")

    # ---- resume_blocks ----
    op.create_table(
        "resume_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("order_index", sa.String(64), nullable=False),
        sa.Column("collapsed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "type IN ('heading','summary','experience','project','skill','education','custom')",
            name="resume_blocks_type_chk",
        ),
        sa.CheckConstraint(
            "length(order_index) > 0 AND length(order_index) < 64",
            name="resume_blocks_order_index_chk",
        ),
    )
    op.create_index(
        "resume_blocks_branch_order_idx",
        "resume_blocks",
        ["branch_id", "order_index"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("resume_blocks_user_deleted_idx", "resume_blocks", ["user_id", "deleted_at"])
    op.create_index("resume_blocks_user_type_idx", "resume_blocks", ["user_id", "type", "deleted_at"])
    _enable_rls("resume_blocks")

    # ---- resume_versions ----
    op.create_table(
        "resume_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("is_full_snapshot", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("base_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("diff_patch", postgresql.JSONB(), nullable=True),
        sa.Column("author_type", sa.Text(), nullable=False, server_default="user"),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("branch_id", "version_no", name="resume_versions_branch_no_unique"),
        sa.CheckConstraint("author_type IN ('user','ai')", name="resume_versions_author_chk"),
        sa.CheckConstraint("trigger IN ('manual','auto','ai')", name="resume_versions_trigger_chk"),
        sa.CheckConstraint(
            "is_full_snapshot = TRUE OR (diff_patch IS NOT NULL AND base_version_id IS NOT NULL AND snapshot_json IS NULL)",
            name="resume_versions_diff_chk",
        ),
        sa.CheckConstraint(
            "is_full_snapshot = FALSE OR (snapshot_json IS NOT NULL AND diff_patch IS NULL)",
            name="resume_versions_full_chk",
        ),
    )
    op.create_index(
        "resume_versions_branch_snapshot_idx",
        "resume_versions",
        ["branch_id", "is_full_snapshot", "version_no"],
    )
    op.create_index("resume_versions_user_created_idx", "resume_versions", ["user_id", "created_at"])
    _enable_rls("resume_versions")


def downgrade() -> None:
    for tbl in [
        "resume_versions",
        "resume_blocks",
        "resume_branches",
        "auth_sessions",
        "user_credentials",
        "users",
    ]:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_user_isolation ON {tbl};")
        op.drop_table(tbl)
