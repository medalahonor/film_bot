"""Leaderboard API routes."""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from api.schemas.leaderboard import ClubStats, LeaderboardEntry, LeaderboardResponse
from api.schemas.movie import MovieResponse
from api.database.models import Movie, Rating, Session, SessionStatus, User, Vote
from api.database.status_manager import STATUS_COMPLETED

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


def _movie_to_response(movie: Movie) -> MovieResponse:
    return MovieResponse(
        id=movie.id,
        session_id=movie.session_id,
        slot=movie.slot,
        kinopoisk_id=movie.kinopoisk_id,
        kinopoisk_url=movie.kinopoisk_url,
        title=movie.title,
        year=movie.year,
        year_end=None,
        type=getattr(movie, 'type', 'film'),
        genres=movie.genres,
        description=movie.description,
        poster_url=movie.poster_url,
        kinopoisk_rating=float(movie.kinopoisk_rating) if movie.kinopoisk_rating is not None else None,
        club_rating=float(movie.club_rating) if movie.club_rating is not None else None,
        trailer_url=getattr(movie, 'trailer_url', None),
        proposer_username=movie.proposer.username if movie.proposer else None,
        proposer_first_name=movie.proposer.first_name if movie.proposer else None,
        proposer_telegram_id=movie.proposer.telegram_id if movie.proposer else None,
        created_at=movie.created_at,
    )


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> LeaderboardResponse:
    completed_session_ids_q = (
        select(Session.id)
        .join(SessionStatus, Session.status_id == SessionStatus.id)
        .where(SessionStatus.code == STATUS_COMPLETED)
    )

    query = (
        select(Movie)
        .where(Movie.session_id.in_(completed_session_ids_q))
        .where(Movie.club_rating.is_not(None))
    )

    if search:
        query = query.where(Movie.title.ilike(f"%{search}%"))

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    movies = list(
        (await db.execute(
            query.order_by(Movie.club_rating.desc()).offset(offset).limit(per_page)
        )).scalars().all()
    )

    # Count votes per movie
    movie_ids = [m.id for m in movies]
    vote_counts: dict[int, int] = {}
    rating_counts: dict[int, int] = {}
    if movie_ids:
        vc = await db.execute(
            select(Vote.movie_id, func.count(Vote.id))
            .where(Vote.movie_id.in_(movie_ids))
            .group_by(Vote.movie_id)
        )
        vote_counts = {row[0]: row[1] for row in vc}
        rc = await db.execute(
            select(Rating.movie_id, func.count(Rating.id))
            .where(Rating.movie_id.in_(movie_ids))
            .group_by(Rating.movie_id)
        )
        rating_counts = {row[0]: row[1] for row in rc}

    items = [
        LeaderboardEntry(
            movie=_movie_to_response(m),
            vote_count=vote_counts.get(m.id, 0),
            rating_count=rating_counts.get(m.id, 0),
        )
        for m in movies
    ]

    return LeaderboardResponse(items=items, total=total, page=page, pages=pages)


@router.get("/stats", response_model=ClubStats)
async def get_club_stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ClubStats:
    completed_ids_q = (
        select(Session.id)
        .join(SessionStatus, Session.status_id == SessionStatus.id)
        .where(SessionStatus.code == STATUS_COMPLETED)
    )

    total_sessions = (
        await db.execute(select(func.count()).select_from(completed_ids_q.subquery()))
    ).scalar() or 0

    total_movies = (
        await db.execute(
            select(func.count(Movie.id)).where(Movie.session_id.in_(completed_ids_q))
        )
    ).scalar() or 0

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    avg_rating_row = (
        await db.execute(
            select(func.avg(Movie.club_rating))
            .where(Movie.session_id.in_(completed_ids_q))
            .where(Movie.club_rating.is_not(None))
        )
    ).scalar()
    avg_club_rating = round(float(avg_rating_row), 2) if avg_rating_row else None

    return ClubStats(
        total_movies=total_movies,
        total_sessions=total_sessions,
        total_users=total_users,
        avg_club_rating=avg_club_rating,
    )
