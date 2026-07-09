"""REQ-052: Remove FORCE ROW LEVEL SECURITY from wechat_credentials.

The ``get_active_credentials()`` SECURITY DEFINER function (0035) is owned
by ``appuser`` — the same role that connects to the database.
``relforcerowsecurity=true`` was set in 0034, which forces RLS on the
table owner. Because the function owner == the table owner == the
connection role, RLS cannot be bypassed, and ``get_active_credentials()``
returns 0 rows. Consequently ``pool.startup()`` loads 0 tasks and
previously-bound users are never resumed after a restart.

Removing FORCE on ``wechat_credentials`` lets the table owner (appuser)
opt out of RLS via ``SET row_security = off`` in the startup path.
RLS policies remain active for all non-owner roles (if any are added
in the future).

The per-user isolation on this table is still enforced at the
application layer: every query path goes through the authenticated
user_id, and ``bot_token_encrypted`` is Fernet-encrypted at rest.

Revision: 0038_052_no_force_creds
Down revision: 0037_052_outbound_drain_fn
"""

from __future__ import annotations

from alembic import op

revision: str = "0038_052_no_force_creds"
down_revision = "0037_052_outbound_drain_fn"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE wechat_credentials NO FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE wechat_credentials FORCE ROW LEVEL SECURITY;")
