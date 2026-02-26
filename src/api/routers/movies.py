"""Movies API routes."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import config
from api.dependencies import get_db, get_current_user
from api.schemas.movie import MovieResponse, ProposeMovieRequest, ReplaceMovieRequest, UpdateClubRatingRequest
from api.telegram_notify import notify_movie_proposed
from api.database.models import Movie, Session, SessionStatus, User
from api.database.repositories import get_movie_by_id, delete_movie_by_id
from api.database.status_manager import STATUS_COLLECTING

router = APIRouter(prefix="/api/movies", tags=["movies"])


def _movie_to_response(movie: Movie) -> MovieResponse:
    return MovieResponse(
        id=movie.id,
        session_id=movie.session_id,
        slot=movie.slot,
        kinopoisk_id=movie.kinopoisk_id,
        kinopoisk_url=movie.kinopoisk_url,
        title=movie.title,
        year=movie.year,
        year_end=movie.year_end,
        type=movie.type,
        genres=movie.genres,
        description=movie.description,
        poster_url=movie.poster_url,
        kinopoisk_rating=float(movie.kinopoisk_rating) if movie.kinopoisk_rating is not None else None,
        club_rating=float(movie.club_rating) if movie.club_rating is not None else None,
        trailer_url=movie.trailer_url,
        proposer_username=movie.proposer.username if movie.proposer else None,
        proposer_first_name=movie.proposer.first_name if movie.proposer else None,
        proposer_last_name=movie.proposer.last_name if movie.proposer else None,
        proposer_telegram_id=movie.proposer.telegram_id if movie.proposer else None,
        created_at=movie.created_at,
    )


async def _get_collecting_session(db: AsyncSession, session_id: int) -> Session:
    """Return session only if it is in 'collecting' status."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    status_result = await db.execute(
        select(SessionStatus).where(SessionStatus.id == session.status_id)
    )
    status = status_result.scalar_one_or_none()
    if not status or status.code != STATUS_COLLECTING:
        raise HTTPException(
            status_code=409,
            detail=f"Session is not in 'collecting' status (current: {status.code if status else 'unknown'})",
        )
    return session


@router.post("/propose", response_model=MovieResponse, status_code=201)
async def propose_movie(
    body: ProposeMovieRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MovieResponse:
    """Propose a movie/serial for the current collecting session."""
    session = await _get_collecting_session(db, body.session_id)

    # Check user doesn't already have a movie in this slot
    slot_conflict = (await db.execute(
        select(Movie)
        .where(Movie.session_id == body.session_id)
        .where(Movie.user_id == user.id)
        .where(Movie.slot == body.slot)
    )).scalar_one_or_none()
    if slot_conflict:
        raise HTTPException(status_code=409, detail="You already proposed a movie for this slot")

    # Check kinopoisk_id uniqueness in this session
    existing = await db.execute(
        select(Movie)
        .where(Movie.session_id == body.session_id)
        .where(Movie.kinopoisk_id == body.kinopoisk_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This movie is already proposed in this session")

    movie = Movie(
        session_id=body.session_id,
        user_id=user.id,
        slot=body.slot,
        kinopoisk_url=body.kinopoisk_url,
        kinopoisk_id=body.kinopoisk_id,
        title=body.title,
        year=body.year,
        year_end=body.year_end,
        type=body.type,
        genres=body.genres,
        description=body.description,
        poster_url=body.poster_url,
        kinopoisk_rating=Decimal(str(body.kinopoisk_rating)) if body.kinopoisk_rating else None,
        trailer_url=body.trailer_url,
    )
    db.add(movie)
    await db.commit()
    await db.refresh(movie)

    # Best-effort notification to the group
    await notify_movie_proposed(
        movie_title=movie.title,
        movie_type=movie.type,
        slot=movie.slot,
        proposer_username=user.username,
        proposer_first_name=user.first_name,
    )

    return _movie_to_response(movie)


@router.put("/{movie_id}", response_model=MovieResponse)
async def replace_movie(
    movie_id: int,
    body: ReplaceMovieRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MovieResponse:
    """Replace a proposed movie or change its slot. Owner or admin only."""
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    is_admin = user.telegram_id in config.telegram_admin_ids
    if not is_admin and movie.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only replace your own movies")

    if not is_admin:
        await _get_collecting_session(db, movie.session_id)

    # If changing slot, check user doesn't have another movie in the target slot
    if body.slot != movie.slot:
        slot_conflict = (await db.execute(
            select(Movie)
            .where(Movie.session_id == movie.session_id)
            .where(Movie.user_id == movie.user_id)
            .where(Movie.slot == body.slot)
            .where(Movie.id != movie_id)
        )).scalar_one_or_none()
        if slot_conflict:
            raise HTTPException(status_code=409, detail="You already have a movie in the target slot")

    # Check kinopoisk_id uniqueness in session (excluding current movie)
    if body.kinopoisk_id != movie.kinopoisk_id:
        existing = (await db.execute(
            select(Movie)
            .where(Movie.session_id == movie.session_id)
            .where(Movie.kinopoisk_id == body.kinopoisk_id)
            .where(Movie.id != movie_id)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="This movie is already proposed in this session")

    movie.slot = body.slot
    movie.kinopoisk_id = body.kinopoisk_id
    movie.kinopoisk_url = body.kinopoisk_url
    movie.title = body.title
    movie.year = body.year
    movie.year_end = body.year_end
    movie.type = body.type
    movie.genres = body.genres
    movie.description = body.description
    movie.poster_url = body.poster_url
    movie.kinopoisk_rating = Decimal(str(body.kinopoisk_rating)) if body.kinopoisk_rating else None
    movie.trailer_url = body.trailer_url

    await db.commit()
    await db.refresh(movie)
    return _movie_to_response(movie)


@router.delete("/{movie_id}", status_code=204)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a movie. Admin or the movie's proposer only."""
    movie = await get_movie_by_id(db, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    is_admin = user.telegram_id in config.telegram_admin_ids
    if not is_admin and movie.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only withdraw your own movies")

    await delete_movie_by_id(db, movie_id)


@router.patch("/{movie_id}/rating", response_model=MovieResponse)
async def update_club_rating(
    movie_id: int,
    body: UpdateClubRatingRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MovieResponse:
    """Admin: manually set club_rating for a movie."""
    if user.telegram_id not in config.telegram_admin_ids:
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    movie.club_rating = Decimal(str(body.club_rating))
    await db.commit()
    await db.refresh(movie)
    return _movie_to_response(movie)
