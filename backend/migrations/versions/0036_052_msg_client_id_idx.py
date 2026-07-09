"""REQ-052 FR-014: partial unique index on agent_messages.client_id.

Every outbound Agent message must carry a client_id (UUID) so iLink can
deduplicate retries. To make accidental client_id reuse impossible at
the DB layer, add a partial unique index covering non-null client_ids.

Inbound messages may have null client_id (iLink only assigns client_id
to outbound). The partial index leaves them out of the constraint.

Revision: 0036_052_agent_messages_client_id_index
Down revision: 0035_052_get_active_credentials_fn
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0036_052_msg_client_id_idx"
down_revision = "0035_052_active_creds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_agent_messages_client_id",
        "agent_messages",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("client_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_messages_client_id", table_name="agent_messages")
