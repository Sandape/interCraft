"""REQ-052 outbound drain — SECURITY DEFINER function.

The agents_outbound_drain ARQ cron needs to scan agent_messages across
all users, but RLS is FORCE'd on appuser. Set row_security = off is
denied for non-superusers. Solution: SECURITY DEFINER function runs
as the function owner (which IS superuser) and bypasses RLS.

Revision: 0037_052_outbound_drain_fn
Down revision: 0036_052_msg_client_id_idx
"""

from __future__ import annotations

from alembic import op

revision: str = "0037_052_outbound_drain_fn"
down_revision = "0036_052_msg_client_id_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing function first (it was created by appuser, so its
    # SECURITY DEFINER context is appuser, which is still subject to RLS).
    op.execute("DROP FUNCTION IF EXISTS get_outbound_drain_candidates(int);")
    # Re-create as postgres (the only superuser). SECURITY DEFINER will
    # then run in postgres's session, which bypasses RLS. The function
    # body is identical to before.
    op.execute(
        """
        CREATE FUNCTION get_outbound_drain_candidates(max_age_hours int)
        RETURNS TABLE (
            id uuid,
            user_id uuid,
            direction text,
            status text,
            content text,
            client_id uuid,
            context_token text,
            wechat_msg_id text,
            created_at timestamptz
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        AS $$
            SELECT
                am.id, am.user_id, am.direction, am.status, am.content,
                am.client_id, am.context_token, am.wechat_msg_id, am.created_at
            FROM public.agent_messages am
            WHERE am.direction = 'outbound'
              AND am.status = 'pending'
              AND am.created_at > NOW() - (max_age_hours || ' hours')::interval
            ORDER BY am.created_at ASC
        $$;
        """
    )
    # Transfer ownership to postgres (the only superuser).
    op.execute("ALTER FUNCTION get_outbound_drain_candidates(int) OWNER TO postgres;")
    op.execute("GRANT EXECUTE ON FUNCTION get_outbound_drain_candidates(int) TO appuser;")


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION get_outbound_drain_candidates(int) FROM appuser;")
    op.execute("DROP FUNCTION IF EXISTS get_outbound_drain_candidates(int);")
