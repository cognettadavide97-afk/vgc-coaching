"""aggiungi vod_link e replay_code a bookings

Revision ID: dcfea9cf2bb0
Revises: f56a5f50b503
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcfea9cf2bb0'
down_revision: Union[str, Sequence[str], None] = 'f56a5f50b503'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('vod_link', sa.String(length=500), nullable=True))
    op.add_column('bookings', sa.Column('replay_code', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bookings', 'replay_code')
    op.drop_column('bookings', 'vod_link')
