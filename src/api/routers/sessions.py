"""Sessions API routes."""
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from api.schemas.movie import MovieResponse
from api.schemas.session import SessionResponse
from api.telegram_notify import notify_session_status_changed
from bot.database.models import Group, Movie, Session, SessionStatus, User
from bot.database.status_manager import STATUS_COLLECTING, STATUS_COMPLETED

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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


def _session_to_response(session: Session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        status=session.status,
        group_telegram_id=session.group.telegram_id,
        created_at=session.created_at,
        voting_started_at=session.voting_started_at,
        completed_at=session.completed_at,
        winner_slot1_id=session.winner_slot1_id,
        winner_slot2_id=session.winner_slot2_id,
        runoff_slot1_ids=json.loads(session.runoff_slot1_ids) if session.runoff_slot1_ids else None,
        runoff_slot2_ids=json.loads(session.runoff_slot2_ids) if session.runoff_slot2_ids else None,
    )


async def _resolve_group(db: AsyncSession, group_telegram_id: int) -> Group:
    result = await db.execute(
        select(Group).where(Group.telegram_id == group_telegram_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


async def _get_active_session(db: AsyncSession, group_id: int) -> Session:
    """Get the most recent non-completed session for a group."""
    completed_id = (
        await db.execute(
            select(SessionStatus.id).where(SessionStatus.code == STATUS_COMPLETED)
        )
    ).scalar()

    q = (
        select(Session)
        .where(Session.group_id == group_id)
        .order_by(Session.created_at.desc())
    )
    if completed_id is not None:
        q = q.where(Session.status_id != completed_id)

    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    return session


@router.get("/current", response_model=SessionResponse)
async def get_current_session(
    group_id: int = Query(..., description="Telegram group ID"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SessionResponse:
    group = await _resolve_group(db, group_id)
    session = await _get_active_session(db, group.id)
    return _session_to_response(session)


@router.get("/current/movies", response_model=List[MovieResponse])
async def get_current_session_movies(
    group_id: int = Query(..., description="Telegram group ID"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> List[MovieResponse]:
    group = await _resolve_group(db, group_id)
    session = await _get_active_session(db, group.id)

    movies = list(
        (await db.execute(
            select(Movie)
            .where(Movie.session_id == session.id)
            .order_by(Movie.slot, Movie.id)
        )).scalars().all()
    )
    return [_movie_to_response(m) for m in movies]


# ---------------------------------------------------------------------------
# Allowed users: create / change status / delete session
# ---------------------------------------------------------------------------

@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionResponse:
    """Create a new collecting session for a group."""
    group_telegram_id: Optional[int] = body.get("group_id")
    if not group_telegram_id:
        raise HTTPException(status_code=422, detail="group_id is required")

    group = await _resolve_group(db, group_telegram_id)

    collecting_status = (
        await db.execute(select(SessionStatus).where(SessionStatus.code == STATUS_COLLECTING))
    ).scalar_one_or_none()
    if not collecting_status:
        raise HTTPException(status_code=500, detail="Session statuses not initialised")

    session = Session(
        group_id=group.id,
        created_by=user.id,
        status_id=collecting_status.id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


@router.patch("/{session_id}/status", response_model=SessionResponse)
async def change_session_status(
    session_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SessionResponse:
    """Change session status."""
    new_status_code: Optional[str] = body.get("status")
    if not new_status_code:
        raise HTTPException(status_code=422, detail="status is required")

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    new_status = (
        await db.execute(select(SessionStatus).where(SessionStatus.code == new_status_code))
    ).scalar_one_or_none()
    if not new_status:
        raise HTTPException(status_code=422, detail=f"Unknown status: {new_status_code}")

    session.status_id = new_status.id
    if new_status_code == STATUS_COMPLETED:
        session.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    await notify_session_status_changed(
        group_telegram_id=session.group.telegram_id,
        new_status=new_status_code,
    )

    return _session_to_response(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """Mark session as completed (soft delete)."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    completed_status = (
        await db.execute(select(SessionStatus).where(SessionStatus.code == STATUS_COMPLETED))
    ).scalar_one_or_none()
    if completed_status:
        session.status_id = completed_status.id
        session.completed_at = datetime.utcnow()
        await db.commit()
