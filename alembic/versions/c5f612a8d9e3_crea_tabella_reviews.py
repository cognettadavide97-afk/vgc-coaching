"""crea tabella reviews e aggiungi review_token/review_email_sent a bookings

Revision ID: c5f612a8d9e3
Revises: b3d84a19e6f2
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f612a8d9e3'
down_revision: Union[str, Sequence[str], None] = 'b3d84a19e6f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('review_token', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_bookings_review_token', 'bookings', ['review_token'])
    op.add_column('bookings', sa.Column('review_email_sent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('bookings', 'review_email_sent', server_default=None)

    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('voto', sa.Integer(), nullable=False),
        sa.Column('commento', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('booking_id')
    )
    op.create_index(op.f('ix_reviews_id'), 'reviews', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_reviews_id'), table_name='reviews')
    op.drop_table('reviews')

    op.drop_column('bookings', 'review_email_sent')
    op.drop_constraint('uq_bookings_review_token', 'bookings', type_='unique')
    op.drop_column('bookings', 'review_token')
