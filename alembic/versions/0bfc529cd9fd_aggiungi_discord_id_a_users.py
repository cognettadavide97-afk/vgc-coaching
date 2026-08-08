"""aggiungi discord_id a users

Revision ID: 0bfc529cd9fd
Revises: 17c843945785
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bfc529cd9fd'
down_revision: Union[str, Sequence[str], None] = '17c843945785'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('discord_id', sa.String(length=30), nullable=True))
    op.create_unique_constraint('uq_users_discord_id', 'users', ['discord_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_users_discord_id', 'users', type_='unique')
    op.drop_column('users', 'discord_id')
