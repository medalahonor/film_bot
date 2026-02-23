"""Admin API routes."""
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_admin
from api.schemas.movie import MovieResponse
from api.schemas.session import SessionResponse
from api.schemas.user import UserResponse
from bot.database.models import Group, Movie, Session, User
from bot.log_handler import get_recent_logs

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    group_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> List[UserResponse]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.get("/users/pending", response_model=List[UserResponse])
async def list_pending_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> List[UserResponse]:
    result = await db.execute(
        select(User)
        .where(User.is_allowed == False)  # noqa: E712
        .order_by(User.created_at.desc())
    )
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/users/{telegram_id}/allow", status_code=200)
async def allow_user(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> dict:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_allowed = True
    await db.commit()
    return {"telegram_id": telegram_id, "is_allowed": True}


@router.post("/users/{telegram_id}/block", status_code=200)
async def block_user(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> dict:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_allowed = False
    await db.commit()
    return {"telegram_id": telegram_id, "is_allowed": False}


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> UserResponse:
    """Manually add a user by telegram_id with is_allowed=True."""
    telegram_id = int(body.get("telegram_id", 0))
    if not telegram_id:
        raise HTTPException(status_code=422, detail="telegram_id is required")
    existing = await db.execute(select(User).where(User.telegram_id == telegram_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(
        telegram_id=telegram_id,
        username=body.get("username"),
        first_name=body.get("first_name"),
        last_name=body.get("last_name"),
        is_allowed=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Session management (admin overview)
# ---------------------------------------------------------------------------

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


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    group_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> List[SessionResponse]:
    q = select(Session).order_by(Session.created_at.desc())
    if group_id is not None:
        group_result = await db.execute(select(Group).where(Group.telegram_id == group_id))
        group = group_result.scalar_one_or_none()
        if group:
            q = q.where(Session.group_id == group.id)
    sessions = list((await db.execute(q)).scalars().all())
    return [_session_to_response(s) for s in sessions]


@router.post("/sessions/{session_id}/set-winner", status_code=200)
async def set_winner(
    session_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> dict:
    """Manually override winners for a session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if "winner_slot1_id" in body:
        session.winner_slot1_id = body["winner_slot1_id"]
    if "winner_slot2_id" in body:
        session.winner_slot2_id = body["winner_slot2_id"]
    await db.commit()
    return {"winner_slot1_id": session.winner_slot1_id, "winner_slot2_id": session.winner_slot2_id}


@router.get("/stats/db", status_code=200)
async def db_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin),
) -> dict:
    from sqlalchemy import func
    from bot.database.models import Rating, Vote
    total_sessions = (await db.execute(select(func.count(Session.id)))).scalar() or 0
    total_movies = (await db.execute(select(func.count(Movie.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_votes = (await db.execute(select(func.count(Vote.id)))).scalar() or 0
    total_ratings = (await db.execute(select(func.count(Rating.id)))).scalar() or 0
    return {
        "sessions": total_sessions,
        "movies": total_movies,
        "users": total_users,
        "votes": total_votes,
        "ratings": total_ratings,
    }


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@router.get("/logs", status_code=200)
async def get_logs(
    n: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(get_admin),
) -> dict:
    """Return the last N log lines from in-memory buffer."""
    return {"logs": get_recent_logs(n)}


# ---------------------------------------------------------------------------
# Batch import
# ---------------------------------------------------------------------------

def _movie_to_response(movie: Movie) -> MovieResponse:
    return MovieResponse(
        id=movie.id,
        session_id=movie.session_id,
        slot=movie.slot,
        kinopoisk_id=movie.kinopoisk_id,
        kinopoisk_url=movie.kinopoisk_url,
        title=movie.title,
        year=movie.year,
        year_end=getattr(movie, 'year_end', None),
        type=getattr(movie, 'type', 'film'),
        genres=movie.genres,
        description=movie.description,
        poster_url=movie.poster_url,
        kinopoisk_rating=float(movie.kinopoisk_rating) if movie.kinopoisk_rating is not None else None,
        club_rating=float(movie.club_rating) if movie.club_rating is not None else None,
        trailer_url=getattr(movie, 'trailer_url', None),
        proposer_username=movie.proposer.username if movie.proposer else None,
        proposer_first_name=movie.proposer.first_name if movie.proposer else None,
        created_at=movie.created_at,
    )


@router.post("/batch-import", status_code=200)
async def batch_import(
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin),
) -> dict:
    """Import multiple movies by Kinopoisk URL into a session.

    Body: {session_id: int, slot: int, urls: list[str]}
    Returns: {imported: [...MovieResponse], errors: [{url, reason}]}
    """
    from bot.services.kinopoisk import parse_movie_data

    session_id: int = int(body.get("session_id", 0))
    slot: int = int(body.get("slot", 1))
    urls: List[str] = body.get("urls", [])

    if not session_id:
        raise HTTPException(status_code=422, detail="session_id is required")
    if slot not in (1, 2):
        raise HTTPException(status_code=422, detail="slot must be 1 or 2")
    if not urls:
        raise HTTPException(status_code=422, detail="urls list is empty")

    session_result = await db.execute(select(Session).where(Session.id == session_id))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    imported: List[MovieResponse] = []
    errors: List[Dict[str, str]] = []

    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            data = await parse_movie_data(url)
            existing = await db.execute(
                select(Movie)
                .where(Movie.session_id == session_id)
                .where(Movie.kinopoisk_id == data["kinopoisk_id"])
            )
            if existing.scalar_one_or_none():
                errors.append({"url": url, "reason": "already exists in session"})
                continue
            movie = Movie(
                session_id=session_id,
                user_id=admin.id,
                slot=slot,
                kinopoisk_url=data["kinopoisk_url"],
                kinopoisk_id=data["kinopoisk_id"],
                title=data["title"],
                year=data.get("year"),
                type=data.get("type", "film"),
                genres=data.get("genres"),
                description=data.get("description"),
                poster_url=data.get("poster_url"),
                kinopoisk_rating=Decimal(str(data["kinopoisk_rating"])) if data.get("kinopoisk_rating") else None,
                trailer_url=data.get("trailer_url"),
            )
            db.add(movie)
            await db.commit()
            await db.refresh(movie)
            imported.append(_movie_to_response(movie))
        except Exception as exc:
            errors.append({"url": url, "reason": str(exc)})

    return {"imported": [m.model_dump() for m in imported], "errors": errors}
