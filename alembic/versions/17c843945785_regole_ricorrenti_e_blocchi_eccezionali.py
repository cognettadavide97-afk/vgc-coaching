"""aggiungi regole ricorrenti, blocchi eccezionali e blocked_admin

Revision ID: 17c843945785
Revises: cc755d0d6a6b
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17c843945785'
down_revision: Union[str, Sequence[str], None] = 'cc755d0d6a6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('slots', sa.Column('blocked_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('slots', 'blocked_admin', server_default=None)

    op.create_table(
        'availability_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('giorno_settimana', sa.Integer(), nullable=False),
        sa.Column('ora_inizio', sa.Time(), nullable=False),
        sa.Column('ora_fine', sa.Time(), nullable=False),
        sa.Column('durata_slot_ore', sa.Integer(), nullable=False),
        sa.Column('attiva', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_availability_rules_id'), 'availability_rules', ['id'], unique=False)

    op.create_table(
        'availability_exceptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data_inizio', sa.Date(), nullable=False),
        sa.Column('data_fine', sa.Date(), nullable=False),
        sa.Column('motivo', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_availability_exceptions_id'), 'availability_exceptions', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_availability_exceptions_id'), table_name='availability_exceptions')
    op.drop_table('availability_exceptions')
    op.drop_index(op.f('ix_availability_rules_id'), table_name='availability_rules')
    op.drop_table('availability_rules')
    op.drop_column('slots', 'blocked_admin')
