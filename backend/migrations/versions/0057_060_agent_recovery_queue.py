"""REQ-060 RLS-safe Agent task recovery queue.

Revision ID: 0057_060_agent_recovery_queue
Revises: 0056_060_wechat_agent_prod
Create Date: 2026-07-13

Final recovery-queue design. The previously designed ``0056_060_agent_task_recovery``
intermediate was retired because its SECURITY DEFINER function scanned the FORCE-RLS
``agent_tasks`` table directly. The reviewed partial unique index
``uq_agent_tasks_resume_from`` and the safe
``get_agent_task_recovery_candidates`` SECURITY DEFINER ACL intent are folded
into this authoritative revision; the unsafe direct scanner revision file itself
is intentionally not added under any revision number.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0057_060_agent_recovery_queue"
down_revision: str | None = "0056_060_wechat_agent_prod"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


FUNCTION_OWNER: str = "postgres"
FUNCTION_SEARCH_PATH: str = "pg_catalog, public"
ALLOWED_APP_ROLE: str = "appuser"


def upgrade() -> None:
    # Reviewed resume-lineage partial unique index folded from the
    # superseded intermediate revision (the superseded file itself is not added).
    op.create_index(
        "uq_agent_tasks_resume_from",
        "agent_tasks",
        ["resume_from_task_id"],
        unique=True,
        postgresql_where=sa.text("resume_from_task_id IS NOT NULL"),
    )

    op.create_table(
        "agent_task_recovery_queue",
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "next_check_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Tenant composite FK mirrors the contract used elsewhere in 0056 so the
    # recovery queue is cross-tenant isolated even if the SECURITY DEFINER
    # recovery helper is revoked or rerouted.
    op.create_foreign_key(
        "fk_agent_task_recovery_queue_task_user",
        "agent_task_recovery_queue",
        "agent_tasks",
        ["task_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "
        f"public.agent_task_recovery_queue TO {FUNCTION_OWNER}"
    )
    op.execute("REVOKE ALL ON TABLE public.agent_task_recovery_queue FROM PUBLIC")
    op.create_index(
        "idx_agent_task_recovery_due",
        "agent_task_recovery_queue",
        ["next_check_at", "task_id"],
    )

    # SECURITY DEFINER trigger owned by the privileged role; uses the canonical
    # pg_catalog + public search path and exposes no direct EXECUTE grant.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.sync_agent_task_recovery_queue()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = {FUNCTION_SEARCH_PATH}
        AS $$
        BEGIN
            IF NEW.status = 'cancel_requested' OR (
                NEW.status IN ('running', 'waiting_external')
                AND NEW.claim_until IS NOT NULL
            ) THEN
                INSERT INTO public.agent_task_recovery_queue (
                    task_id, user_id, next_check_at, updated_at
                ) VALUES (
                    NEW.id,
                    NEW.user_id,
                    CASE
                        WHEN NEW.status = 'cancel_requested' THEN now()
                        ELSE NEW.claim_until
                    END,
                    now()
                )
                ON CONFLICT (task_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    next_check_at = EXCLUDED.next_check_at,
                    updated_at = now();
            ELSE
                DELETE FROM public.agent_task_recovery_queue
                WHERE task_id = NEW.id;
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(f"ALTER FUNCTION public.sync_agent_task_recovery_queue() OWNER TO {FUNCTION_OWNER}")
    op.execute(
        """
        CREATE TRIGGER trg_agent_task_recovery_queue
        AFTER INSERT OR UPDATE OF status, claim_until, user_id
        ON public.agent_tasks
        FOR EACH ROW EXECUTE FUNCTION public.sync_agent_task_recovery_queue()
        """
    )

    # One-time backfill so the queue is consistent immediately after upgrade.
    op.execute(
        """
        INSERT INTO public.agent_task_recovery_queue (
            task_id, user_id, next_check_at, updated_at
        )
        SELECT
            id,
            user_id,
            CASE
                WHEN status = 'cancel_requested' THEN now()
                ELSE claim_until
            END,
            now()
        FROM public.agent_tasks
        WHERE status = 'cancel_requested'
           OR (
               status IN ('running', 'waiting_external')
               AND claim_until IS NOT NULL
           )
        ON CONFLICT (task_id) DO NOTHING
        """
    )

    # Narrow queue-backed recovery discovery. SECURITY DEFINER + fixed
    # search_path + intended privileged owner + least-privilege ACL.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.get_agent_task_recovery_candidates(max_count integer)
        RETURNS TABLE (task_id uuid, user_id uuid)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = {FUNCTION_SEARCH_PATH}
        AS $$
            SELECT queued.task_id, queued.user_id
            FROM public.agent_task_recovery_queue AS queued
            WHERE queued.next_check_at <= now()
            ORDER BY queued.next_check_at ASC, queued.task_id ASC
            LIMIT LEAST(GREATEST(max_count, 1), 1000)
        $$
        """
    )
    op.execute(
        f"ALTER FUNCTION public.get_agent_task_recovery_candidates(integer) OWNER TO {FUNCTION_OWNER}"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.get_agent_task_recovery_candidates(integer) FROM PUBLIC"
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION public.get_agent_task_recovery_candidates(integer) FROM {ALLOWED_APP_ROLE}"
    )
    op.execute(
        f"GRANT EXECUTE ON FUNCTION public.get_agent_task_recovery_candidates(integer) TO {ALLOWED_APP_ROLE}"
    )
    op.execute("REVOKE ALL ON FUNCTION public.sync_agent_task_recovery_queue() FROM PUBLIC")
    op.execute(
        f"REVOKE ALL ON FUNCTION public.sync_agent_task_recovery_queue() FROM {ALLOWED_APP_ROLE}"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.get_agent_task_recovery_candidates(integer)")
    op.execute("DROP TRIGGER IF EXISTS trg_agent_task_recovery_queue ON agent_tasks")
    op.execute("DROP FUNCTION IF EXISTS public.sync_agent_task_recovery_queue()")
    op.drop_index("idx_agent_task_recovery_due", table_name="agent_task_recovery_queue")
    op.drop_table("agent_task_recovery_queue")
    op.drop_index("uq_agent_tasks_resume_from", table_name="agent_tasks")
