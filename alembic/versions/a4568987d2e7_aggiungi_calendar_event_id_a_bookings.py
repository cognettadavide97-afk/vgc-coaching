"""aggiungi calendar_event_id a bookings

Revision ID: a4568987d2e7
Revises: 1972ef07e768
Create Date: 2026-07-06 17:01:44.689497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4568987d2e7'
down_revision: Union[str, Sequence[str], None] = '1972ef07e768'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('calendar_event_id', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bookings', 'calendar_event_id')
