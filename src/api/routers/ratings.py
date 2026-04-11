"""Ratings API routes."""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from api.schemas.rating import (
    OpenMovieRatings,
    OpenRatingsResponse,
    RaterInfo,
    RatingRequest,
    RatingResponse,
)
from api.database.models import Movie, Rating, Session, SessionStatus, User
from api.database.status_manager import STATUS_RATING
from api.session_events import notify_session_changed

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


@router.get("/my", response_model=List[RatingResponse])
async def get_my_ratings(
    session_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[RatingResponse]:
    result = await db.execute(
        select(Rating)
        .where(Rating.session_id == session_id)
        .where(Rating.user_id == user.id)
        .order_by(Rating.id)
    )
    ratings = list(result.scalars().all())
    return [
        RatingResponse(
            id=r.id,
            session_id=r.session_id,
            movie_id=r.movie_id,
            rating=r.rating,
            created_at=r.created_at,
        )
        for r in ratings
    ]


@router.post("", response_model=RatingResponse, status_code=201)
async def submit_rating(
    body: RatingRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RatingResponse:
    """Submit or update a rating 1-10 for a movie. Recalculates club_rating."""
    # Validate session is in rating status
    session_result = await db.execute(select(Session).where(Session.id == body.session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    status_result = await db.execute(
        select(SessionStatus).where(SessionStatus.id == session.status_id)
    )
    status = status_result.scalar_one_or_none()
    if not status or status.code != STATUS_RATING:
        raise HTTPException(
            status_code=409,
            detail=f"Session is not in 'rating' status (current: {status.code if status else 'unknown'})",
        )

    # Validate movie belongs to this session
    movie_result = await db.execute(select(Movie).where(Movie.id == body.movie_id))
    movie = movie_result.scalar_one_or_none()
    if not movie or movie.session_id != body.session_id:
        raise HTTPException(status_code=404, detail="Movie not found in this session")

    # No-op guard: if the user resubmits the same value, skip the write
    existing_result = await db.execute(
        select(Rating)
        .where(Rating.session_id == body.session_id)
        .where(Rating.movie_id == body.movie_id)
        .where(Rating.user_id == user.id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None and existing.rating == body.rating:
        response.status_code = 200
        return RatingResponse(
            id=existing.id,
            session_id=existing.session_id,
            movie_id=existing.movie_id,
            rating=existing.rating,
            created_at=existing.created_at,
        )

    # Upsert: delete old rating and insert new
    await db.execute(
        delete(Rating)
        .where(Rating.session_id == body.session_id)
        .where(Rating.movie_id == body.movie_id)
        .where(Rating.user_id == user.id)
    )
    rating = Rating(
        session_id=body.session_id,
        movie_id=body.movie_id,
        user_id=user.id,
        rating=body.rating,
    )
    db.add(rating)
    await db.flush()  # get the id

    # Recalculate club_rating = average of all ratings for this movie
    avg_result = await db.execute(
        select(func.avg(Rating.rating)).where(Rating.movie_id == body.movie_id)
    )
    avg = avg_result.scalar()
    if avg is not None:
        movie.club_rating = Decimal(str(round(float(avg), 2)))

    await db.commit()
    await db.refresh(rating)

    await notify_session_changed({
        "type": "rating_updated",
        "movie_id": body.movie_id,
        "club_rating": float(movie.club_rating) if movie.club_rating is not None else None,
    })

    return RatingResponse(
        id=rating.id,
        session_id=rating.session_id,
        movie_id=rating.movie_id,
        rating=rating.rating,
        created_at=rating.created_at,
    )


def _build_rater_info(rating_obj: Rating) -> RaterInfo:
    user = rating_obj.user
    return RaterInfo(
        telegram_id=user.telegram_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        rating=rating_obj.rating,
        created_at=rating_obj.created_at,
    )


@router.get("/open/{session_id}", response_model=OpenRatingsResponse)
async def get_open_ratings(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OpenRatingsResponse:
    """All ratings per movie with rater details, sorted by created_at desc."""
    result = await db.execute(
        select(Rating)
        .where(Rating.session_id == session_id)
        .order_by(Rating.movie_id, Rating.created_at.desc())
    )
    ratings_list = list(result.scalars().all())

    grouped: dict[int, list[RaterInfo]] = {}
    for r in ratings_list:
        grouped.setdefault(r.movie_id, []).append(_build_rater_info(r))

    # Get club_rating from movies
    movie_ids = list(grouped.keys())
    club_ratings: dict[int, float | None] = {}
    if movie_ids:
        movie_rows = await db.execute(
            select(Movie.id, Movie.club_rating).where(Movie.id.in_(movie_ids))
        )
        club_ratings = {
            row[0]: float(row[1]) if row[1] is not None else None
            for row in movie_rows
        }

    results = [
        OpenMovieRatings(
            movie_id=mid,
            club_rating=club_ratings.get(mid),
            raters=raters,
        )
        for mid, raters in grouped.items()
    ]
    return OpenRatingsResponse(session_id=session_id, results=results)


@router.get("/movie/{movie_id}", response_model=List[RaterInfo])
async def get_movie_ratings(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> List[RaterInfo]:
    """All ratings for a single movie, sorted by rating descending."""
    result = await db.execute(
        select(Rating)
        .where(Rating.movie_id == movie_id)
        .order_by(Rating.rating.desc(), Rating.created_at.asc())
    )
    return [_build_rater_info(r) for r in result.scalars().all()]
