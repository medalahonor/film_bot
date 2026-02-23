"""Add is_allowed to users.

Revision ID: 006
Revises: 005
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'is_allowed',
            sa.Boolean,
            nullable=False,
            server_default=text('true'),
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_allowed')
