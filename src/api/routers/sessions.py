"""Sessions API routes."""
import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete as sql_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import validate_init_data
from api.dependencies import get_admin, get_db, get_current_user
from api.schemas.movie import MovieResponse
from api.schemas.session import SessionResponse
from api.session_events import notify_session_changed, subscribe, unsubscribe
from api.telegram_notify import notify_session_status_changed
from api.database.models import Movie, Rating, Session, SessionStatus, User, Vote
from api.database.status_manager import STATUS_COLLECTING, STATUS_COMPLETED, STATUS_RATING, STATUS_VOTING

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Order used to detect rollback direction
_STATUS_ORDER = {STATUS_COLLECTING: 0, STATUS_VOTING: 1, STATUS_RATING: 2, STATUS_COMPLETED: 3}


def _parse_json_ids(raw: Optional[str]) -> Optional[list[int]]:
    """Safely parse a JSON-encoded list of ints stored in a text column."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


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
        proposer_last_name=movie.proposer.last_name if movie.proposer else None,
        proposer_telegram_id=movie.proposer.telegram_id if movie.proposer else None,
        created_at=movie.created_at,
    )


def _session_to_response(session: Session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        status=session.status,
        created_at=session.created_at,
        voting_started_at=session.voting_started_at,
        completed_at=session.completed_at,
        winner_slot1_id=session.winner_slot1_id,
        winner_slot2_id=session.winner_slot2_id,
        runoff_slot1_ids=_parse_json_ids(session.runoff_slot1_ids),
        runoff_slot2_ids=_parse_json_ids(session.runoff_slot2_ids),
    )


async def _get_active_session(db: AsyncSession) -> Session:
    """Get the most recent non-completed session (global)."""
    completed_id = (
        await db.execute(
            select(SessionStatus.id).where(SessionStatus.code == STATUS_COMPLETED)
        )
    ).scalar()

    q = select(Session).order_by(Session.created_at.desc())
    if completed_id is not None:
        q = q.where(Session.status_id != completed_id)

    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    return session


async def _clear_rollback_data(db: AsyncSession, session: Session, new_status_code: str) -> None:
    """Clear data that no longer belongs to the rolled-back status."""
    current_order = _STATUS_ORDER.get(session.status, -1)
    new_order = _STATUS_ORDER.get(new_status_code, -1)
    if new_order >= current_order:
        return  # Not a rollback — nothing to clear

    # Rolling back to voting or earlier: clear ratings, winners, runoff
    if new_order <= _STATUS_ORDER[STATUS_VOTING]:
        await db.execute(sql_delete(Rating).where(Rating.session_id == session.id))
        session.winner_slot1_id = None
        session.winner_slot2_id = None
        session.runoff_slot1_ids = None
        session.runoff_slot2_ids = None
        session.completed_at = None

    # Rolling back to collecting: also clear votes
    if new_order <= _STATUS_ORDER[STATUS_COLLECTING]:
        await db.execute(sql_delete(Vote).where(Vote.session_id == session.id))


@router.get("/current", response_model=SessionResponse)
async def get_current_session(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SessionResponse:
    session = await _get_active_session(db)
    return _session_to_response(session)


@router.get("/current/movies", response_model=List[MovieResponse])
async def get_current_session_movies(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> List[MovieResponse]:
    session = await _get_active_session(db)

    movies = list(
        (await db.execute(
            select(Movie)
            .where(Movie.session_id == session.id)
            .order_by(Movie.slot, Movie.id)
        )).scalars().all()
    )
    return [_movie_to_response(m) for m in movies]


@router.get("/events")
async def session_events(
    init_data: str = Query("", description="Telegram WebApp initData"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream: pushes session-changed events to connected clients.

    NOTE: Requires --workers 1. With multiple workers, in-process pub/sub
    won't cross process boundaries. Use Redis pub/sub for multi-worker setup.
    """
    tg_user = validate_init_data(init_data)

    from sqlalchemy import select as _select
    from api.database.models import User as _User
    from api.config import config

    telegram_id = int(tg_user["id"])
    result = await db.execute(_select(_User).where(_User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    queue: asyncio.Queue = asyncio.Queue()
    subscribe(queue)

    async def _generate() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Allowed users: create / change status / delete session
# ---------------------------------------------------------------------------

@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionResponse:
    """Create a new global collecting session."""
    collecting_status = (
        await db.execute(select(SessionStatus).where(SessionStatus.code == STATUS_COLLECTING))
    ).scalar_one_or_none()
    if not collecting_status:
        raise HTTPException(status_code=500, detail="Session statuses not initialised")

    session = Session(
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
    """Change session status. On rollback, clears data from future statuses."""
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

    current_order = _STATUS_ORDER.get(session.status, -1)
    new_order = _STATUS_ORDER.get(new_status_code, -1)

    # Guard 1: forward → voting requires at least one proposed movie
    if new_status_code == STATUS_VOTING and new_order > current_order:
        movie_count = (
            await db.execute(
                select(func.count(Movie.id)).where(Movie.session_id == session_id)
            )
        ).scalar() or 0
        if movie_count == 0:
            raise HTTPException(status_code=409, detail="Cannot start voting: no movies proposed")

    # Guard 2: forward → rating requires winners for all slots that have movies
    if new_status_code == STATUS_RATING and new_order > current_order:
        slot1_count = (
            await db.execute(
                select(func.count(Movie.id))
                .where(Movie.session_id == session_id, Movie.slot == 1)
            )
        ).scalar() or 0
        slot2_count = (
            await db.execute(
                select(func.count(Movie.id))
                .where(Movie.session_id == session_id, Movie.slot == 2)
            )
        ).scalar() or 0
        missing = []
        if slot1_count > 0 and not session.winner_slot1_id:
            missing.append("slot 1")
        if slot2_count > 0 and not session.winner_slot2_id:
            missing.append("slot 2")
        if missing:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot start rating: no winners for {', '.join(missing)}",
            )

    await _clear_rollback_data(db, session, new_status_code)

    session.status_id = new_status.id
    if new_status_code == STATUS_COMPLETED:
        session.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    await notify_session_status_changed(new_status=new_status_code)
    await notify_session_changed(_session_to_response(session).model_dump(mode="json"))

    return _session_to_response(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_admin),
) -> None:
    """Hard-delete a session and all its data (movies, votes, ratings). Admin only."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.execute(sql_delete(Rating).where(Rating.session_id == session_id))
    await db.execute(sql_delete(Vote).where(Vote.session_id == session_id))
    await db.execute(sql_delete(Movie).where(Movie.session_id == session_id))
    await db.delete(session)
    await db.commit()

    await notify_session_changed({"deleted": True, "id": session_id})
