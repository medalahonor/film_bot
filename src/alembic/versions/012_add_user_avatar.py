"""Add avatar and avatar_updated_at to users.

Revision ID: 012
Revises: 011
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('avatar', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('avatar_updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'avatar_updated_at')
    op.drop_column('users', 'avatar')
