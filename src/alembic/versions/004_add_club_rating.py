"""add club_rating to movies for storing the film club average rating

Revision ID: 004
Revises: 003
Create Date: 2026-02-08 12:00:00.000000

"""
# pylint: disable=no-member,invalid-name
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add club_rating column to movies table."""
    op.add_column(
        'movies',
        sa.Column('club_rating', sa.DECIMAL(4, 2), nullable=True),
    )


def downgrade() -> None:
    """Remove club_rating column from movies table."""
    op.drop_column('movies', 'club_rating')
