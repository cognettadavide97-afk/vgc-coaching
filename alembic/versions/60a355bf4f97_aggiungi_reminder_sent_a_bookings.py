"""aggiungi reminder_sent a bookings

Revision ID: 60a355bf4f97
Revises: dcfea9cf2bb0
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60a355bf4f97'
down_revision: Union[str, Sequence[str], None] = 'dcfea9cf2bb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('reminder_sent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('bookings', 'reminder_sent', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bookings', 'reminder_sent')
