"""add poll IDs and movie mappings to sessions for tracking votes

Revision ID: 003
Revises: 002
Create Date: 2026-02-06 18:00:00.000000

"""
# pylint: disable=no-member,invalid-name
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add columns for storing Telegram poll IDs and movie-to-option mappings."""
    op.add_column(
        'sessions',
        sa.Column('poll_slot1_id', sa.String(255), nullable=True),
    )
    op.add_column(
        'sessions',
        sa.Column('poll_slot2_id', sa.String(255), nullable=True),
    )
    op.add_column(
        'sessions',
        sa.Column('poll_slot1_movie_ids', sa.Text(), nullable=True),
    )
    op.add_column(
        'sessions',
        sa.Column('poll_slot2_movie_ids', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove poll ID and movie mapping columns."""
    op.drop_column('sessions', 'poll_slot2_movie_ids')
    op.drop_column('sessions', 'poll_slot1_movie_ids')
    op.drop_column('sessions', 'poll_slot2_id')
    op.drop_column('sessions', 'poll_slot1_id')
