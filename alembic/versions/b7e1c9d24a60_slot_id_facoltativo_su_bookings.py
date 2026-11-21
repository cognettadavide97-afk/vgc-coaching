"""slot_id facoltativo su bookings

Revision ID: b7e1c9d24a60
Revises: 8d2f4b6a1e93
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1c9d24a60'
down_revision: Union[str, Sequence[str], None] = '8d2f4b6a1e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Dal pezzo 4.4 una prenotazione può nascere da un orario, senza slot.
    # La chiave esterna resta: quando c'è, lo slot deve esistere.
    op.alter_column('bookings', 'slot_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Fallisce se esistono già prenotazioni senza slot: è giusto, tornare
    # indietro richiederebbe di inventare uno slot per ciascuna.
    op.alter_column('bookings', 'slot_id', existing_type=sa.Integer(), nullable=False)
