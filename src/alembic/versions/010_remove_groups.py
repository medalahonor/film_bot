"""Remove groups table and group_id from sessions (sessions are now global).

Revision ID: 010
Revises: 009
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop FK constraint and group_id column from sessions
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.drop_constraint('sessions_group_id_fkey', type_='foreignkey')
        batch_op.drop_column('group_id')

    # Drop groups table
    op.drop_table('groups')


def downgrade() -> None:
    op.create_table(
        'groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id'),
    )
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'sessions_group_id_fkey', 'groups', ['group_id'], ['id']
        )
