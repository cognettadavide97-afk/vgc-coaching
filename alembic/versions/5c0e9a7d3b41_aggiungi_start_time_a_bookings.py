"""aggiungi start_time a bookings

Revision ID: 5c0e9a7d3b41
Revises: 2eac6f32b19b
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c0e9a7d3b41'
down_revision: Union[str, Sequence[str], None] = '2eac6f32b19b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Tre passi perché una colonna obbligatoria non si può aggiungere a una
    # tabella che ha già righe: nascerebbero senza valore. Prima facoltativa,
    # poi riempita con l'ora dello slot di ogni prenotazione, infine
    # obbligatoria. slot_id è NOT NULL con chiave esterna, quindi ogni
    # prenotazione ha uno slot e nessuna resta vuota.
    op.add_column('bookings', sa.Column('start_time', sa.DateTime(), nullable=True))
    # Sottoquery e non UPDATE ... JOIN: la stessa frase vale su MySQL e su
    # SQLite.
    op.execute(
        "UPDATE bookings SET start_time = "
        "(SELECT slots.start_time FROM slots WHERE slots.id = bookings.slot_id)"
    )
    op.alter_column('bookings', 'start_time', existing_type=sa.DateTime(), nullable=False)
    op.create_index(op.f('ix_bookings_start_time'), 'bookings', ['start_time'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bookings_start_time'), table_name='bookings')
    op.drop_column('bookings', 'start_time')
