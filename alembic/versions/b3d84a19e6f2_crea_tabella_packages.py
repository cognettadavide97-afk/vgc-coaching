"""crea tabella packages e aggiungi package_id a bookings

Revision ID: b3d84a19e6f2
Revises: a1c92f7e4b18
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d84a19e6f2'
down_revision: Union[str, Sequence[str], None] = 'a1c92f7e4b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('sessioni_totali', sa.Integer(), nullable=False),
        sa.Column('sessioni_usate', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('durata_sessione_ore', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('prezzo_cents', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.alter_column('packages', 'sessioni_usate', server_default=None)
    op.alter_column('packages', 'durata_sessione_ore', server_default=None)
    op.create_index(op.f('ix_packages_id'), 'packages', ['id'], unique=False)

    op.add_column('bookings', sa.Column('package_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_bookings_package_id', 'bookings', 'packages', ['package_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_bookings_package_id', 'bookings', type_='foreignkey')
    op.drop_column('bookings', 'package_id')

    op.drop_index(op.f('ix_packages_id'), table_name='packages')
    op.drop_table('packages')
