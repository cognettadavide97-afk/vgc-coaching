"""crea tabella ore_prenotate

Revision ID: 8d2f4b6a1e93
Revises: 5c0e9a7d3b41
Create Date: 2026-11-21 00:00:00.000000

"""
from datetime import timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d2f4b6a1e93'
down_revision: Union[str, Sequence[str], None] = '5c0e9a7d3b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    tabella = op.create_table(
        'ore_prenotate',
        sa.Column('inizio', sa.DateTime(), nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('inizio'),
    )
    # Indice prima della chiave esterna: MySQL ne crea uno da sé per ogni
    # chiave esterna che non ne trova già uno, e l'ordine inverso lascerebbe
    # due indici identici sulla stessa colonna.
    op.create_index(op.f('ix_ore_prenotate_booking_id'), 'ore_prenotate', ['booking_id'], unique=False)
    op.create_foreign_key(
        'fk_ore_prenotate_booking_id', 'ore_prenotate', 'bookings',
        ['booking_id'], ['id'], ondelete='CASCADE'
    )

    # Le ore delle prenotazioni esistenti: una riga per ogni ora di ogni
    # prenotazione non cancellata, no-show compresi (occupano ancora la loro
    # ora). Calcolate in Python e non in SQL: la somma di un'ora a una data
    # si scrive diversamente su MySQL e su SQLite. Misurato in produzione il
    # 2026-11-21: nessuna ora venduta due volte, quindi la chiave primaria
    # non rifiuta nulla.
    prenotazioni = op.get_bind().execute(sa.text(
        "SELECT id, start_time, duration_hours FROM bookings WHERE status <> 'cancelled'"
    )).all()
    righe = [
        {"inizio": inizio + timedelta(hours=ora), "booking_id": booking_id}
        for booking_id, inizio, durata in prenotazioni
        for ora in range(durata)
    ]
    if righe:
        op.bulk_insert(tabella, righe)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ore_prenotate')
