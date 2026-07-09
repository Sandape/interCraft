"""0030 — REQ-048 analytics_events table (埋点表 + RLS).

Adds the analytics_events table for埋点 (mode_selected, drill_selected,
drill_degraded_to_bm25, drill_degraded_to_llm_rerank, doubao_card_rendered,
variant_mode_enabled, variant_generation_failed, drill_resink_completed).

RLS policy mirrors the existing app-scoped pattern: ``app.user_id`` GUC
matches ``user_id`` column.

Revision ID: 0030_analytics_events
Revises: 0029_error_questions_embedding
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "0030_analytics_events"
down_revision: Union[str, Sequence[str], None] = "0029_error_questions_embedding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics_events table + RLS + indexes."""
    op.create_table(
        "analytics_events",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Index on (user_id, event_type, created_at DESC) for time-window queries.
    op.create_index(
        "idx_analytics_events_user_type_created",
        "analytics_events",
        ["user_id", "event_type", sa.text("created_at DESC")],
        unique=False,
    )
    # RLS: app-scoped, matching the existing pattern from other tables.
    op.execute("ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS analytics_events_user_isolation ON analytics_events"
    )
    op.execute(
        "CREATE POLICY analytics_events_user_isolation ON analytics_events "
        "USING (current_setting('app.user_id', true)::uuid = user_id) "
        "WITH CHECK (current_setting('app.user_id', true)::uuid = user_id)"
    )


def downgrade() -> None:
    """Reverse migration."""
    op.execute("DROP POLICY IF EXISTS analytics_events_user_isolation ON analytics_events")
    op.execute("ALTER TABLE analytics_events DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_analytics_events_user_type_created", table_name="analytics_events")
    op.drop_table("analytics_events")