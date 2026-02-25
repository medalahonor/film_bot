"""Allow movies without session (global library).

Revision ID: 011
Revises: 010
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('movies', 'session_id', nullable=True)
    op.alter_column('movies', 'slot', nullable=True)
    op.alter_column('movies', 'user_id', nullable=True)
    # Partial unique index: prevent duplicate kinopoisk_id in library entries
    op.execute(
        "CREATE UNIQUE INDEX uq_library_kinopoisk ON movies (kinopoisk_id) "
        "WHERE session_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_library_kinopoisk")
    op.alter_column('movies', 'user_id', nullable=False,
                    existing_type=sa.Integer(), existing_nullable=True)
    op.alter_column('movies', 'slot', nullable=False,
                    existing_type=sa.Integer(), existing_nullable=True)
    op.alter_column('movies', 'session_id', nullable=False,
                    existing_type=sa.Integer(), existing_nullable=True)
