"""Create REQ-035 admin console and observability tables."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0025_035_admin_observability"
down_revision = "0024_033_eval_pm_dashboard"
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
    op.create_table(
        "admin_access_grants",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("role_label", sa.Text(), nullable=False),
        sa.Column("capabilities", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("environment_scope", sa.Text(), nullable=False, server_default=sa.text("'all'")),
        sa.Column("granted_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_admin_access_grants_user_active", "admin_access_grants", ["user_id", "revoked_at", "expires_at"])
    op.create_index("idx_admin_access_grants_environment", "admin_access_grants", ["environment_scope"])
    _enable_rls("admin_access_grants")

    op.create_table(
        "admin_audit_events",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("visibility_mode", sa.Text(), nullable=False, server_default=sa.text("'aggregate'")),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_admin_audit_events_actor_created", "admin_audit_events", ["actor_id", "created_at"])
    op.create_index("idx_admin_audit_events_target", "admin_audit_events", ["target_type", "target_id"])
    op.create_index("idx_admin_audit_events_action", "admin_audit_events", ["action"])

    op.create_table(
        "dashboard_snapshots",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("format", sa.Text(), nullable=False, server_default=sa.text("'markdown'")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("filters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("warnings", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("privacy_status", sa.Text(), nullable=False, server_default=sa.text("'safe'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_dashboard_snapshots_created_by", "dashboard_snapshots", ["created_by", "created_at"])
    op.create_index("idx_dashboard_snapshots_privacy", "dashboard_snapshots", ["privacy_status"])

    op.create_table(
        "observability_traces",
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("business_event_id", sa.Text(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=False, server_default=sa.text("'local'")),
        sa.Column("feature_area", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_context", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("trace_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_observability_traces_user_started", "observability_traces", ["user_id", "started_at"])
    op.create_index("idx_observability_traces_business_event", "observability_traces", ["business_event_id"])
    op.create_index("idx_observability_traces_environment", "observability_traces", ["environment"])
    op.create_index("idx_observability_traces_status", "observability_traces", ["status"])
    _enable_rls("observability_traces")

    op.create_table(
        "observability_spans",
        sa.Column("span_id", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("parent_span_id", sa.Text(), nullable=True),
        sa.Column("agent_run_id", sa.Text(), nullable=True),
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column("span_kind", sa.Text(), nullable=False, server_default=sa.text("'node'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_payload_id", sa.Text(), nullable=True),
        sa.Column("output_payload_id", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("span_id"),
        sa.ForeignKeyConstraint(["trace_id"], ["observability_traces.trace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_observability_spans_trace_started", "observability_spans", ["trace_id", "started_at"])
    op.create_index("idx_observability_spans_parent", "observability_spans", ["parent_span_id"])
    op.create_index("idx_observability_spans_node", "observability_spans", ["node_name"])
    op.create_index("idx_observability_spans_user_started", "observability_spans", ["user_id", "started_at"])
    _enable_rls("observability_spans")

    op.create_table(
        "observability_payloads",
        sa.Column("payload_id", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("span_id", sa.Text(), nullable=True),
        sa.Column("payload_kind", sa.Text(), nullable=False),
        sa.Column("visibility_mode", sa.Text(), nullable=False, server_default=sa.text("'redacted'")),
        sa.Column("redacted_summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("shape", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("masked_raw", JSONB(), nullable=True),
        sa.Column("secret_scan_status", sa.Text(), nullable=False, server_default=sa.text("'passed'")),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("payload_id"),
        sa.ForeignKeyConstraint(["trace_id"], ["observability_traces.trace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["span_id"], ["observability_spans.span_id"], ondelete="SET NULL"),
    )
    op.create_index("idx_observability_payloads_trace", "observability_payloads", ["trace_id"])
    op.create_index("idx_observability_payloads_span", "observability_payloads", ["span_id"])
    op.create_index("idx_observability_payloads_retention", "observability_payloads", ["retention_expires_at"])
    op.create_index("idx_observability_payloads_visibility", "observability_payloads", ["visibility_mode"])
    _enable_rls("observability_payloads")

    op.create_table(
        "llm_call_records",
        sa.Column("llm_call_id", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("span_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("provider_request_id", sa.Text(), nullable=True),
        sa.Column("request_payload_id", sa.Text(), nullable=True),
        sa.Column("response_payload_id", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'success'")),
        sa.Column("safe_curl", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("llm_call_id"),
        sa.ForeignKeyConstraint(["trace_id"], ["observability_traces.trace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["span_id"], ["observability_spans.span_id"], ondelete="SET NULL"),
    )
    op.create_index("idx_llm_call_records_trace", "llm_call_records", ["trace_id"])
    op.create_index("idx_llm_call_records_span", "llm_call_records", ["span_id"])
    op.create_index("idx_llm_call_records_model", "llm_call_records", ["model"])
    op.create_index("idx_llm_call_records_user_started", "llm_call_records", ["user_id", "started_at"])
    _enable_rls("llm_call_records")

    op.create_table(
        "tool_operation_records",
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("span_id", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False, server_default=sa.text("'tool'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'success'")),
        sa.Column("input_payload_id", sa.Text(), nullable=True),
        sa.Column("output_payload_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("operation_id"),
        sa.ForeignKeyConstraint(["trace_id"], ["observability_traces.trace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["span_id"], ["observability_spans.span_id"], ondelete="SET NULL"),
    )
    op.create_index("idx_tool_operation_records_trace", "tool_operation_records", ["trace_id"])
    op.create_index("idx_tool_operation_records_span", "tool_operation_records", ["span_id"])
    op.create_index("idx_tool_operation_records_tool", "tool_operation_records", ["tool_name"])
    op.create_index("idx_tool_operation_records_user_started", "tool_operation_records", ["user_id", "started_at"])
    _enable_rls("tool_operation_records")

    op.create_table(
        "observability_eval_runs",
        sa.Column("eval_run_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("pass_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("eval_run_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_observability_eval_runs_user_started", "observability_eval_runs", ["user_id", "started_at"])
    op.create_index("idx_observability_eval_runs_status", "observability_eval_runs", ["status"])
    _enable_rls("observability_eval_runs")

    op.create_table(
        "observability_eval_case_results",
        sa.Column("case_result_id", sa.Text(), nullable=False),
        sa.Column("eval_run_id", sa.Text(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("score", sa.Numeric(6, 4), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("llm_call_id", sa.Text(), nullable=True),
        sa.Column("badcase_id", sa.Text(), nullable=True),
        sa.Column("metrics", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("case_result_id"),
        sa.ForeignKeyConstraint(["eval_run_id"], ["observability_eval_runs.eval_run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_observability_eval_cases_run", "observability_eval_case_results", ["eval_run_id"])
    op.create_index("idx_observability_eval_cases_trace", "observability_eval_case_results", ["trace_id"])
    op.create_index("idx_observability_eval_cases_llm", "observability_eval_case_results", ["llm_call_id"])
    op.create_index("idx_observability_eval_cases_badcase", "observability_eval_case_results", ["badcase_id"])
    _enable_rls("observability_eval_case_results")

    op.create_table(
        "observability_coverage_gaps",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("feature_area", sa.Text(), nullable=False),
        sa.Column("flow_name", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("accepted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_observability_coverage_gaps_flow", "observability_coverage_gaps", ["feature_area", "flow_name"])
    op.create_index("idx_observability_coverage_gaps_severity", "observability_coverage_gaps", ["severity"])
    op.create_index("idx_observability_coverage_gaps_status", "observability_coverage_gaps", ["status"])


def downgrade() -> None:
    for table in [
        "observability_coverage_gaps",
        "observability_eval_case_results",
        "observability_eval_runs",
        "tool_operation_records",
        "llm_call_records",
        "observability_payloads",
        "observability_spans",
        "observability_traces",
        "dashboard_snapshots",
        "admin_audit_events",
        "admin_access_grants",
    ]:
        op.drop_table(table)
