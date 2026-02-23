"""Add year_end to movies.

Revision ID: 008
Revises: 007
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'movies',
        sa.Column('year_end', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('movies', 'year_end')
