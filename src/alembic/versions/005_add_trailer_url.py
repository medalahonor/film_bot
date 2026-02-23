"""Add trailer_url to movies.

Revision ID: 005
Revises: 004
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('movies', sa.Column('trailer_url', sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column('movies', 'trailer_url')
