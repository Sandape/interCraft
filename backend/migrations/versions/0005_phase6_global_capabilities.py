"""Phase 6 — global capabilities: lifecycle fields, audit_logs, export_tasks, content tables, subscription_plans.

Revision ID: 0005_phase6_global_capabilities
Revises: 0004_phase4_agent
Create Date: 2026-06-15

Adds: role/scheduled_purge_at/cancellation_deadline to users,
audit_logs (partitioned by month), export_tasks, resources, help_faq,
subscription_plans with seed data.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_phase6_global_capabilities"
down_revision = "0004_phase4_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 1. User table changes ----
    op.add_column(
        "users",
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("scheduled_purge_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("cancellation_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    # Relax the status CHECK to include all lifecycle states
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_chk;")
    op.create_check_constraint(
        "users_status_chk",
        "users",
        sa.text("status IN ('active','soft_deleted','purged','frozen','deleted')"),
    )
    op.create_check_constraint(
        "users_role_chk",
        "users",
        sa.text("role IN ('user','admin')"),
    )

    # ---- 2. audit_logs (partitioned by month) ----
    op.execute(
        """CREATE TABLE audit_logs (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            actor_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id UUID,
            old_values JSONB,
            new_values JSONB,
            ip_address TEXT,
            user_agent TEXT,
            token_usage INTEGER,
            duration_ms INTEGER,
            node_input_summary TEXT,
            node_output_summary TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);"""
    )
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;")
    op.execute(
        """CREATE POLICY audit_logs_user_isolation ON audit_logs
            USING (actor_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (actor_id = NULLIF(current_setting('app.user_id', true), '')::uuid);"""
    )
    # Create initial partition (current month)
    op.execute(
        """CREATE TABLE audit_logs_202606 PARTITION OF audit_logs
            FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');"""
    )
    # Create next month's partition
    op.execute(
        """CREATE TABLE audit_logs_202607 PARTITION OF audit_logs
            FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');"""
    )
    # Indexes on audit_logs
    op.create_index("audit_logs_actor_created_idx", "audit_logs", ["actor_id", sa.text("created_at DESC")])
    op.create_index("audit_logs_resource_idx", "audit_logs", ["resource_type", "resource_id", sa.text("created_at DESC")])
    op.create_index("audit_logs_action_created_idx", "audit_logs", ["action", sa.text("created_at DESC")])
    op.create_index("audit_logs_created_idx", "audit_logs", [sa.text("created_at DESC")])

    # ---- 3. export_tasks ----
    op.create_table(
        "export_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("include_types", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="export_tasks_status_chk",
        ),
    )
    op.create_index("export_tasks_user_created_idx", "export_tasks", ["user_id", sa.text("created_at DESC")])
    _enable_rls("export_tasks")

    # ---- 4. resources ----
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False, server_default="article"),
        sa.Column("read_time_minutes", sa.Integer(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('interview_tips','resume_guide','tech_prep')",
            name="resources_category_chk",
        ),
        sa.CheckConstraint(
            "content_type IN ('article','video','template')",
            name="resources_content_type_chk",
        ),
    )
    op.create_index("resources_category_sort_idx", "resources", ["category", "sort_order"])
    op.execute("CREATE INDEX resources_tags_gin_idx ON resources USING GIN(tags);")
    op.execute(
        "CREATE INDEX resources_search_idx ON resources "
        "USING GIN(to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(summary, '')));"
    )

    # ---- 5. help_faq ----
    op.create_table(
        "help_faq",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('account','interview','resume','subscription','technical')",
            name="help_faq_category_chk",
        ),
    )
    op.create_index("help_faq_category_sort_idx", "help_faq", ["category", "sort_order"])
    op.execute(
        "CREATE INDEX help_faq_search_idx ON help_faq "
        "USING GIN(to_tsvector('simple', coalesce(question, '') || ' ' || coalesce(answer, '')));"
    )

    # ---- 6. subscription_plans (seed data) ----
    op.create_table(
        "subscription_plans",
        sa.Column("plan", sa.Text(), primary_key=True),
        sa.Column("monthly_token_quota", sa.Integer(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "plan IN ('free','pro','enterprise')",
            name="subscription_plans_plan_chk",
        ),
    )
    op.execute(
        """INSERT INTO subscription_plans (plan, monthly_token_quota, features) VALUES
            ('free', 500000, '{}'),
            ('pro', 5000000, '{"priority_support": true}'),
            ('enterprise', 50000000, '{"priority_support": true, "custom_quota": true}');"""
    )


def downgrade() -> None:
    # Reverse order
    op.execute("DELETE FROM subscription_plans;")
    op.drop_table("subscription_plans")
    op.drop_table("help_faq")
    op.drop_table("resources")
    op.drop_table("export_tasks")
    op.execute("DROP TABLE IF EXISTS audit_logs_202606 CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_logs_202607 CASCADE;")
    op.drop_table("audit_logs")
    op.drop_constraint("users_role_chk", "users")
    op.drop_column("users", "cancellation_deadline")
    op.drop_column("users", "scheduled_purge_at")
    op.drop_column("users", "role")


def _enable_rls(table: str, policy_column: str = "user_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING ({policy_column} = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK ({policy_column} = current_setting('app.user_id', true)::uuid);"
    )
