"""merge_052_053

Revision ID: d39a0181498c
Revises: 0038_052_no_force_creds, 0046_053_interview_research
Create Date: 2026-07-09 11:55:16.884446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd39a0181498c'
down_revision: Union[str, Sequence[str], None] = ('0038_052_no_force_creds', '0046_053_interview_research')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
