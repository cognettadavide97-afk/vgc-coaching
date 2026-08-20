"""categoria al posto di showdown_username su users

Revision ID: a1c92f7e4b18
Revises: 0bfc529cd9fd
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c92f7e4b18'
down_revision: Union[str, Sequence[str], None] = '0bfc529cd9fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('categoria', sa.String(length=20), nullable=True))
    op.drop_column('users', 'showdown_username')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('showdown_username', sa.String(length=100), nullable=True))
    op.drop_column('users', 'categoria')
