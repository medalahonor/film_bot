"""Repository functions for database access.

All repeated database queries used by handlers should go through this
module to avoid duplication and keep the handler layer thin.
"""
import logging
import math
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.database.models import User, Session, Movie, Rating, Vote
from api.database.status_manager import get_status_by_code, STATUS_COMPLETED

logger = logging.getLogger(__name__)


async def get_or_create_user(
    db: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> User:
    """Get an existing user or create a new one."""
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created new user: %d", telegram_id)
    return user


async def get_user_by_username(
    db: AsyncSession,
    username: str,
) -> Optional[User]:
    """Get a user by their Telegram username."""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_active_session(
    db: AsyncSession,
    status_code: str,
) -> Optional[Session]:
    """Get the most recent session with a specific status (global, no group filter)."""
    status = await get_status_by_code(db, status_code)
    if not status:
        return None
    result = await db.execute(
        select(Session)
        .where(Session.status_id == status.id)
        .order_by(Session.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_active_session_any(
    db: AsyncSession,
) -> Optional[Session]:
    """Get any active (non-completed) session (global, no group filter)."""
    completed_status = await get_status_by_code(db, STATUS_COMPLETED)
    if not completed_status:
        return None
    result = await db.execute(
        select(Session)
        .where(Session.status_id != completed_status.id)
        .order_by(Session.created_at.desc())
    )
    return result.scalar_one_or_none()


# ── Movie queries ────────────────────────────────────────────────────────


async def get_movies_paginated(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 5,
) -> Tuple[List[Movie], int]:
    """Get movies ordered by newest first with pagination.

    Returns:
        Tuple of (movies_list, total_pages).
    """
    total = (await db.execute(select(func.count(Movie.id)))).scalar() or 0
    total_pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    result = await db.execute(
        select(Movie)
        .order_by(Movie.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    return list(result.scalars().all()), total_pages


async def search_movies_by_title(
    db: AsyncSession,
    query: str,
    limit: int = 10,
) -> List[Movie]:
    """Search movies by title (case-insensitive LIKE)."""
    result = await db.execute(
        select(Movie)
        .where(Movie.title.ilike(f"%{query}%"))
        .order_by(Movie.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_movie_by_id(
    db: AsyncSession,
    movie_id: int,
) -> Optional[Movie]:
    """Get a movie by its primary key."""
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    return result.scalar_one_or_none()


async def delete_movie_by_id(db: AsyncSession, movie_id: int) -> bool:
    """Delete a movie and its related votes/ratings.

    Also clears winner references in the parent session.
    Returns True if the movie was found and deleted.
    """
    movie = await get_movie_by_id(db, movie_id)
    if not movie:
        return False

    session = movie.session

    # Clear winner references if this movie was a winner
    if session.winner_slot1_id == movie_id:
        session.winner_slot1_id = None
    if session.winner_slot2_id == movie_id:
        session.winner_slot2_id = None

    # Delete related records
    await db.execute(sa_delete(Rating).where(Rating.movie_id == movie_id))
    await db.execute(sa_delete(Vote).where(Vote.movie_id == movie_id))
    await db.delete(movie)
    await db.commit()
    return True


async def get_movie_avg_rating(db: AsyncSession, movie_id: int) -> float:
    """Get average rating for a movie from Rating records."""
    result = await db.execute(
        select(func.avg(Rating.rating)).where(Rating.movie_id == movie_id)
    )
    avg = result.scalar()
    return round(float(avg), 2) if avg else 0.0


async def recalc_club_rating(db: AsyncSession, movie_id: int) -> Optional[float]:
    """Recalculate and store club_rating from Rating records.

    Returns the new average, or None if there are no ratings.
    """
    result = await db.execute(
        select(func.avg(Rating.rating)).where(Rating.movie_id == movie_id)
    )
    avg = result.scalar()

    movie = await get_movie_by_id(db, movie_id)
    if movie:
        movie.club_rating = round(float(avg), 2) if avg else None
        await db.commit()

    return round(float(avg), 2) if avg else None


async def _get_or_create_system_user(db: AsyncSession) -> User:
    """Get or create the primary system placeholder user (telegram_id = -1)."""
    result = await db.execute(
        select(User).where(User.telegram_id == -1)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=-1,
            username="system",
            first_name="System",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


# ── Session management ───────────────────────────────────────────────────


async def set_session_status(
    db: AsyncSession,
    session: Session,
    status_code: str,
) -> bool:
    """Change session status. Returns False if target status not found."""
    new_status = await get_status_by_code(db, status_code)
    if not new_status:
        return False
    session.status_id = new_status.id
    if status_code == STATUS_COMPLETED:
        session.completed_at = datetime.utcnow()
    await db.commit()
    return True


async def get_session_movies(
    db: AsyncSession,
    session_id: int,
) -> List[Movie]:
    """Get all movies for a session ordered by slot."""
    result = await db.execute(
        select(Movie)
        .where(Movie.session_id == session_id)
        .order_by(Movie.slot, Movie.id)
    )
    return list(result.scalars().all())


async def create_completed_session_for_import(
    db: AsyncSession,
    created_by_id: int,
) -> Session:
    """Create a completed session for batch import."""
    completed_status = await get_status_by_code(db, STATUS_COMPLETED)
    now = datetime.utcnow()
    session = Session(
        created_by=created_by_id,
        status_id=completed_status.id,
        created_at=now,
        completed_at=now,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session
