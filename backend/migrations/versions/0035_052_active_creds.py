"""REQ-052 T031: Create get_active_credentials() SECURITY DEFINER function.

The iLink connection pool (app.channels.ilink_pool) uses this function on
startup to discover which users have active iLink bot credentials and need
their long-poll tasks resumed. Without it, the pool silently fails
(startup() catches the UndefinedFunctionError) and 0 tasks spawn, which
means previously-bound users receive no inbound messages after a restart.

The function reads ``wechat_credentials WHERE status='active'`` while
bypassing the per-user RLS policy (because the pool runs in a no-rls
session). SECURITY DEFINER is required so the policy check is skipped
without granting BYPASSRLS to the appuser role.

Revision: 0035_052_get_active_credentials_fn
Down revision: 0034_052_agent_tables
"""

from __future__ import annotations

from alembic import op

revision: str = "0035_052_active_creds"
down_revision = "0034_052_agent_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DROP first to avoid the "cannot change return type of existing
    # function" error when a previous version of this function exists
    # with a different signature (some test environments created it ad-hoc
    # before this migration existed).
    op.execute("DROP FUNCTION IF EXISTS get_active_credentials();")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_active_credentials()
        RETURNS TABLE (user_id uuid, cursor text)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        AS $$
            SELECT wc.user_id, wc.cursor
            FROM public.wechat_credentials wc
            WHERE wc.status = 'active'
              AND wc.bot_token_encrypted IS NOT NULL
        $$;
        """
    )
    # SECURITY DEFINER runs as the function owner (typically the migration
    # runner). Grant EXECUTE to appuser so the iLink pool's no-rls session
    # can call it without BYPASSRLS privilege.
    op.execute("GRANT EXECUTE ON FUNCTION get_active_credentials() TO appuser;")


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION get_active_credentials() FROM appuser;")
    op.execute("DROP FUNCTION IF EXISTS get_active_credentials();")
