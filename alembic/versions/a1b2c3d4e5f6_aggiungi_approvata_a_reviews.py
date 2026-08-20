"""aggiungi approvata a reviews

Revision ID: a1b2c3d4e5f6
Revises: d4a72e0f8b31
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd4a72e0f8b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default='0' (non solo default=False lato Python) perché le
    # recensioni GIÀ esistenti nel database, scritte prima che questa
    # colonna esistesse, devono restare non pubbliche finché il coach non le
    # approva esplicitamente — non possiamo lasciarle NULL né farle
    # comparire subito come approvate.
    op.add_column('reviews', sa.Column('approvata', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reviews', 'approvata')
