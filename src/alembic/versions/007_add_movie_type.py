"""Add type to movies.

Revision ID: 007
Revises: 006
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: add column with server_default so existing rows get 'film'
    op.add_column(
        'movies',
        sa.Column('type', sa.String(20), nullable=False, server_default='film'),
    )
    # Step 2: remove server_default — the field is mandatory at application level
    op.alter_column('movies', 'type', server_default=None)


def downgrade() -> None:
    op.drop_column('movies', 'type')
