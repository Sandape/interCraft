"""Phase 2 entities — 7 tables + RLS policies.

Revision ID: 0002_phase2_entities
Revises: 0001_initial
Create Date: 2026-06-13

Creates: interview_sessions / error_questions / ability_dimensions /
ability_dimensions_history / jobs / tasks / activities
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_phase2_entities"
down_revision = "0001_initial"
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


def upgrade() -> None:
    # ---- interview_sessions (E-13) ----
    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resume_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("thread_id", sa.Text(), nullable=True),
        sa.Column("checkpoint_ns", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("overall_score", sa.Numeric(4, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','running','completed','aborted')", name="interview_sessions_status_chk"),
        sa.CheckConstraint("mode IS NULL OR mode IN ('text','voice')", name="interview_sessions_mode_chk"),
        sa.CheckConstraint("duration_sec IS NULL OR duration_sec >= 0", name="interview_sessions_duration_chk"),
        sa.CheckConstraint("overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 10)", name="interview_sessions_score_chk"),
    )
    op.create_index("interview_sessions_user_started_idx", "interview_sessions", ["user_id", sa.text("started_at DESC NULLS LAST")])
    op.create_index("interview_sessions_user_status_idx", "interview_sessions", ["user_id", "status"])
    op.execute(
        "CREATE UNIQUE INDEX interview_sessions_thread_unique "
        "ON interview_sessions (thread_id, checkpoint_ns) WHERE thread_id IS NOT NULL;"
    )
    _enable_rls("interview_sessions")

    # ---- error_questions (E-7) ----
    op.create_table(
        "error_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dimension", sa.Text(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("reference_answer_md", sa.Text(), nullable=True),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="fresh"),
        sa.Column("frequency", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('fresh','practicing','mastered','archived')", name="error_questions_status_chk"),
        sa.CheckConstraint("frequency BETWEEN 0 AND 3", name="error_questions_freq_chk"),
        sa.CheckConstraint("score IS NULL OR (score BETWEEN 0 AND 10)", name="error_questions_score_chk"),
        sa.CheckConstraint("length(question_text) BETWEEN 1 AND 2000", name="error_questions_text_chk"),
        sa.CheckConstraint(
            "dimension IS NULL OR dimension IN ('tech_depth','architecture','engineering_practice','communication','algorithm','business')",
            name="error_questions_dim_chk",
        ),
    )
    op.create_index("error_questions_user_status_freq_idx", "error_questions", ["user_id", "status", sa.text("frequency DESC")])
    op.create_index("error_questions_user_dim_idx", "error_questions", ["user_id", "dimension"])
    op.create_index("error_questions_user_created_idx", "error_questions", ["user_id", sa.text("created_at DESC")])
    op.create_index("error_questions_user_practiced_idx", "error_questions", ["user_id", sa.text("last_practiced_at DESC")],
                     postgresql_where=sa.text("last_practiced_at IS NOT NULL"))
    _enable_rls("error_questions")

    # ---- ability_dimensions (E-8) ----
    op.create_table(
        "ability_dimensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension_key", sa.Text(), nullable=False),
        sa.Column("actual_score", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("ideal_score", sa.Numeric(4, 2), nullable=False, server_default="10.00"),
        sa.Column("sub_scores", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "dimension_key IN ('tech_depth','architecture','engineering_practice','communication','algorithm','business')",
            name="ability_dimensions_key_chk",
        ),
        sa.CheckConstraint("actual_score BETWEEN 0 AND 10", name="ability_dimensions_actual_chk"),
        sa.CheckConstraint("ideal_score BETWEEN 0 AND 10", name="ability_dimensions_ideal_chk"),
        sa.CheckConstraint("source IN ('manual','interview','error','coach')", name="ability_dimensions_source_chk"),
        sa.UniqueConstraint("user_id", "dimension_key", name="ability_dimensions_user_key_unique"),
    )
    op.create_index("ability_dimensions_user_updated_idx", "ability_dimensions", ["user_id", sa.text("last_updated_at DESC")])
    _enable_rls("ability_dimensions")

    # ---- ability_dimensions_history (E-9) ----
    op.create_table(
        "ability_dimensions_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension_key", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("aggregate", sa.Text(), nullable=False),
        sa.Column("actual_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("ideal_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("aggregate IN ('month','day')", name="ability_history_agg_chk"),
        sa.CheckConstraint(
            "dimension_key IN ('tech_depth','architecture','engineering_practice','communication','algorithm','business')",
            name="ability_history_key_chk",
        ),
        sa.CheckConstraint("actual_score BETWEEN 0 AND 10", name="ability_history_actual_chk"),
        sa.CheckConstraint("ideal_score BETWEEN 0 AND 10", name="ability_history_ideal_chk"),
        sa.UniqueConstraint("user_id", "dimension_key", "aggregate", "snapshot_date", name="ability_history_user_dim_agg_date_unique"),
    )
    op.create_index("ability_history_user_dim_agg_date_idx", "ability_dimensions_history",
                     ["user_id", "dimension_key", "aggregate", sa.text("snapshot_date DESC")])
    _enable_rls("ability_dimensions_history")

    # ---- jobs (E-12) ----
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=False),
        sa.Column("jd_url", sa.Text(), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resume_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="applied"),
        sa.Column("status_history", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_status_changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notes_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('applied','test','oa','hr','offer','rejected','withdrawn')", name="jobs_status_chk"),
        sa.CheckConstraint("length(company) BETWEEN 1 AND 100", name="jobs_company_chk"),
        sa.CheckConstraint("length(position) BETWEEN 1 AND 100", name="jobs_position_chk"),
        sa.CheckConstraint("jd_url IS NULL OR jd_url ~ '^https?://'", name="jobs_jd_url_chk"),
    )
    op.create_index("jobs_user_status_changed_idx", "jobs", ["user_id", "status", sa.text("last_status_changed_at DESC")])
    op.create_index("jobs_user_created_idx", "jobs", ["user_id", sa.text("created_at DESC")])
    op.create_index("jobs_user_branch_idx", "jobs", ["user_id", "branch_id"], postgresql_where=sa.text("branch_id IS NOT NULL"))
    _enable_rls("jobs")

    # ---- tasks (E-10) ----
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=True),
        sa.Column("related_entity_type", sa.Text(), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="todo"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('interview_prep','branch_optimize','application_followup','manual')", name="tasks_type_chk"),
        sa.CheckConstraint("status IN ('todo','doing','done','archived')", name="tasks_status_chk"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 200", name="tasks_title_chk"),
        sa.CheckConstraint(
            "related_entity_type IN ('job','branch','error_question') OR (related_entity_type IS NULL AND type='manual')",
            name="tasks_entity_type_chk",
        ),
    )
    op.create_index("tasks_user_status_due_idx", "tasks", ["user_id", "status", "due_at"])
    op.create_index("tasks_user_entity_idx", "tasks", ["user_id", "related_entity_type", "related_entity_id"],
                     postgresql_where=sa.text("related_entity_id IS NOT NULL"))
    op.execute(
        "CREATE UNIQUE INDEX tasks_user_type_entity_unique "
        "ON tasks (user_id, type, related_entity_id) WHERE related_entity_id IS NOT NULL;"
    )
    _enable_rls("tasks")

    # ---- activities (E-11) ----
    op.create_table(
        "activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False, server_default="user"),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "type IN ('task_created','task_completed','job_created','job_status_changed','interview_started','interview_completed','branch_created','error_logged','manual')",
            name="activities_type_chk",
        ),
        sa.CheckConstraint("actor_type IN ('user','system','agent')", name="activities_actor_chk"),
    )
    op.create_index("activities_user_occurred_idx", "activities", ["user_id", sa.text("occurred_at DESC"), sa.text("id DESC")])
    op.create_index("activities_user_type_occurred_idx", "activities", ["user_id", "type", sa.text("occurred_at DESC")])
    _enable_rls("activities")


def downgrade() -> None:
    for tbl in [
        "activities",
        "tasks",
        "jobs",
        "ability_dimensions_history",
        "ability_dimensions",
        "error_questions",
        "interview_sessions",
    ]:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_user_isolation ON {tbl};")
        op.drop_table(tbl)
