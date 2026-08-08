"""aggiungi service_type a bookings

Revision ID: 98489ff817ea
Revises: d1af2a35c949
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98489ff817ea'
down_revision: Union[str, Sequence[str], None] = 'd1af2a35c949'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default temporaneo per backfillare le righe esistenti (dati di test,
    # nessun dato reale da preservare); poi la colonna resta NOT NULL senza default,
    # ogni nuova prenotazione deve specificare esplicitamente il servizio.
    op.add_column('bookings', sa.Column('service_type', sa.String(length=30), nullable=False, server_default='vod_review'))
    op.alter_column('bookings', 'service_type', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bookings', 'service_type')
