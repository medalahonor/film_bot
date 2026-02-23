"""Add runoff_slot1_ids and runoff_slot2_ids to sessions.

Revision ID: 009
Revises: 008
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('runoff_slot1_ids', sa.Text(), nullable=True))
    op.add_column('sessions', sa.Column('runoff_slot2_ids', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'runoff_slot2_ids')
    op.drop_column('sessions', 'runoff_slot1_ids')
