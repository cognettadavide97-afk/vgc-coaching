"""aggiungi slot_id_secondario a bookings

Revision ID: d4a72e0f8b31
Revises: c5f612a8d9e3
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a72e0f8b31'
down_revision: Union[str, Sequence[str], None] = 'c5f612a8d9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('slot_id_secondario', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_bookings_slot_id_secondario', 'bookings', 'slots', ['slot_id_secondario'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_bookings_slot_id_secondario', 'bookings', type_='foreignkey')
    op.drop_column('bookings', 'slot_id_secondario')
