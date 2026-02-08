"""add rating message IDs to sessions

Revision ID: 002
Revises: 001
Create Date: 2026-02-06 12:00:00.000000

"""
# pylint: disable=no-member,invalid-name
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add columns for tracking rating interface messages."""
    op.add_column(
        'sessions',
        sa.Column('rating_msg_slot1_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'sessions',
        sa.Column('rating_msg_slot2_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'sessions',
        sa.Column('rating_scoreboard_msg_id', sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    """Remove rating message ID columns."""
    op.drop_column('sessions', 'rating_scoreboard_msg_id')
    op.drop_column('sessions', 'rating_msg_slot2_id')
    op.drop_column('sessions', 'rating_msg_slot1_id')
