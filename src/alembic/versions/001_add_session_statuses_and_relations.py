"""add session_statuses and relations

Revision ID: 001
Revises: 
Create Date: 2026-02-04 12:00:00.000000

"""
# pylint: disable=no-member,invalid-name
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = '000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # 1. Create session_statuses table
    op.create_table(
        'session_statuses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    # 2. Insert default statuses
    op.execute("""
        INSERT INTO session_statuses (code, name, description) VALUES
        ('collecting', 'Сбор предложений', 'Участники предлагают фильмы для голосования'),
        ('voting', 'Голосование', 'Идет голосование за предложенные фильмы'),
        ('rating', 'Выставление рейтингов', 'Участники оценивают просмотренные фильмы'),
        ('completed', 'Завершена', 'Сессия завершена')
    """)
    
    # 3. Add status_id to sessions table
    op.add_column('sessions', sa.Column('status_id', sa.Integer(), nullable=True))
    
    # 4. Migrate data: set status_id based on old status field
    op.execute("""
        UPDATE sessions
        SET status_id = (
            SELECT id FROM session_statuses 
            WHERE code = sessions.status
        )
    """)
    
    # 5. Make status_id NOT NULL
    op.alter_column('sessions', 'status_id', nullable=False)
    
    # 6. Add foreign key
    op.create_foreign_key(
        'fk_sessions_status', 
        'sessions', 
        'session_statuses',
        ['status_id'], 
        ['id']
    )
    
    # 7. Drop old status column
    op.drop_column('sessions', 'status')
    
    # 8. Add session_id to votes table
    op.add_column('votes', sa.Column('session_id', sa.Integer(), nullable=True))
    
    # 9. Populate session_id in votes from movies
    op.execute("""
        UPDATE votes
        SET session_id = (
            SELECT session_id FROM movies
            WHERE movies.id = votes.movie_id
        )
    """)
    
    # 10. Make session_id NOT NULL
    op.alter_column('votes', 'session_id', nullable=False)
    
    # 11. Add foreign key for votes
    op.create_foreign_key(
        'fk_votes_session',
        'votes',
        'sessions',
        ['session_id'],
        ['id']
    )
    
    # 12. Drop old constraint and add new one for votes
    op.drop_constraint('uq_movie_user_vote', 'votes', type_='unique')
    op.create_unique_constraint(
        'uq_session_movie_user_vote',
        'votes',
        ['session_id', 'movie_id', 'user_id']
    )
    
    # 13. Add session_id to ratings table
    op.add_column('ratings', sa.Column('session_id', sa.Integer(), nullable=True))
    
    # 14. Populate session_id in ratings from movies
    op.execute("""
        UPDATE ratings
        SET session_id = (
            SELECT session_id FROM movies
            WHERE movies.id = ratings.movie_id
        )
    """)
    
    # 15. Make session_id NOT NULL
    op.alter_column('ratings', 'session_id', nullable=False)
    
    # 16. Add foreign key for ratings
    op.create_foreign_key(
        'fk_ratings_session',
        'ratings',
        'sessions',
        ['session_id'],
        ['id']
    )
    
    # 17. Drop old constraint and add new one for ratings
    op.drop_constraint('uq_movie_user_rating', 'ratings', type_='unique')
    op.create_unique_constraint(
        'uq_session_movie_user_rating',
        'ratings',
        ['session_id', 'movie_id', 'user_id']
    )


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Ratings: revert changes
    op.drop_constraint('uq_session_movie_user_rating', 'ratings', type_='unique')
    op.create_unique_constraint('uq_movie_user_rating', 'ratings', ['movie_id', 'user_id'])
    op.drop_constraint('fk_ratings_session', 'ratings', type_='foreignkey')
    op.drop_column('ratings', 'session_id')
    
    # Votes: revert changes
    op.drop_constraint('uq_session_movie_user_vote', 'votes', type_='unique')
    op.create_unique_constraint('uq_movie_user_vote', 'votes', ['movie_id', 'user_id'])
    op.drop_constraint('fk_votes_session', 'votes', type_='foreignkey')
    op.drop_column('votes', 'session_id')
    
    # Sessions: revert changes
    op.add_column('sessions', sa.Column('status', sa.String(length=50), nullable=True))
    
    # Restore status values from status_id
    op.execute("""
        UPDATE sessions
        SET status = (
            SELECT code FROM session_statuses
            WHERE id = sessions.status_id
        )
    """)
    
    op.alter_column('sessions', 'status', nullable=False)
    op.drop_constraint('fk_sessions_status', 'sessions', type_='foreignkey')
    op.drop_column('sessions', 'status_id')
    
    # Drop session_statuses table
    op.drop_table('session_statuses')
