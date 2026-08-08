"""aggiungi blocked_external a slots

Revision ID: f56a5f50b503
Revises: 37a82dbead86
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f56a5f50b503'
down_revision: Union[str, Sequence[str], None] = '37a82dbead86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('slots', sa.Column('blocked_external', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('slots', 'blocked_external', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('slots', 'blocked_external')
