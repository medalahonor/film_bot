"""Votes API routes."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from api.schemas.vote import MovieVoteResult, VoteRequest, VoteResponse, VoteResultsResponse
from api.telegram_notify import notify_voting_finalized
from bot.database.models import Movie, Session, SessionStatus, User, Vote
from bot.database.status_manager import STATUS_RATING, STATUS_VOTING

router = APIRouter(prefix="/api/votes", tags=["votes"])


@router.get("/my", response_model=List[VoteResponse])
async def get_my_votes(
    session_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[VoteResponse]:
    result = await db.execute(
        select(Vote)
        .where(Vote.session_id == session_id)
        .where(Vote.user_id == user.id)
        .order_by(Vote.id)
    )
    votes = list(result.scalars().all())
    return [
        VoteResponse(
            id=v.id,
            session_id=v.session_id,
            movie_id=v.movie_id,
            created_at=v.created_at,
        )
        for v in votes
    ]


@router.post("", response_model=List[VoteResponse], status_code=201)
async def submit_votes(
    body: VoteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[VoteResponse]:
    """Submit votes for a slot (replaces all previous votes in that slot)."""
    session_result = await db.execute(select(Session).where(Session.id == body.session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    status_result = await db.execute(
        select(SessionStatus).where(SessionStatus.id == session.status_id)
    )
    status = status_result.scalar_one_or_none()
    if not status or status.code != STATUS_VOTING:
        raise HTTPException(
            status_code=409,
            detail=f"Session is not in 'voting' status (current: {status.code if status else 'unknown'})",
        )

    # In runoff mode: restrict voting to only the runoff movie IDs for that slot
    runoff_ids: Optional[List[int]] = None
    if body.slot == 1 and session.runoff_slot1_ids:
        runoff_ids = json.loads(session.runoff_slot1_ids)
    elif body.slot == 2 and session.runoff_slot2_ids:
        runoff_ids = json.loads(session.runoff_slot2_ids)

    if runoff_ids is not None:
        valid_movie_ids = set(runoff_ids)
    else:
        slot_movies_result = await db.execute(
            select(Movie.id)
            .where(Movie.session_id == body.session_id)
            .where(Movie.slot == body.slot)
        )
        valid_movie_ids = {row[0] for row in slot_movies_result}

    invalid = set(body.movie_ids) - valid_movie_ids
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Movie IDs {invalid} do not belong to slot {body.slot} in this session",
        )

    # Replace previous votes for this user in this slot
    await db.execute(
        delete(Vote)
        .where(Vote.session_id == body.session_id)
        .where(Vote.user_id == user.id)
        .where(Vote.movie_id.in_(valid_movie_ids))
    )

    new_votes = [
        Vote(session_id=body.session_id, movie_id=mid, user_id=user.id)
        for mid in body.movie_ids
    ]
    db.add_all(new_votes)
    await db.commit()
    for v in new_votes:
        await db.refresh(v)

    return [
        VoteResponse(id=v.id, session_id=v.session_id, movie_id=v.movie_id, created_at=v.created_at)
        for v in new_votes
    ]


@router.get("/results/{session_id}", response_model=VoteResultsResponse)
async def get_vote_results(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VoteResultsResponse:
    """Aggregated vote counts per movie for a session."""
    rows = await db.execute(
        select(Vote.movie_id, func.count(Vote.id).label("cnt"))
        .where(Vote.session_id == session_id)
        .group_by(Vote.movie_id)
        .order_by(func.count(Vote.id).desc())
    )
    results = [MovieVoteResult(movie_id=row[0], vote_count=row[1]) for row in rows]
    return VoteResultsResponse(session_id=session_id, results=results)


def _find_slot_result(
    vote_rows: list,
    slot_movie_ids: list[int],
) -> tuple[Optional[int], list[int]]:
    """Returns (winner_id or None, runoff_ids).

    winner_id is set when there is a clear winner.
    runoff_ids is set when multiple movies are tied at the top.
    If slot is empty — returns (None, []).
    If slot has one movie — that movie wins by default.
    """
    if not slot_movie_ids:
        return None, []
    if len(slot_movie_ids) == 1:
        return slot_movie_ids[0], []

    counts = {row[0]: row[1] for row in vote_rows}
    all_counts = [(mid, counts.get(mid, 0)) for mid in slot_movie_ids]
    max_count = max(c for _, c in all_counts)
    top = [mid for mid, c in all_counts if c == max_count]

    if len(top) == 1:
        return top[0], []
    return None, top


@router.post("/finalize/{session_id}", status_code=200)
async def finalize_votes(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Count votes, detect ties, set winners or start runoff. Available to all allowed users."""
    session_result = await db.execute(select(Session).where(Session.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    status_result = await db.execute(
        select(SessionStatus).where(SessionStatus.id == session.status_id)
    )
    status = status_result.scalar_one_or_none()
    if not status or status.code != STATUS_VOTING:
        raise HTTPException(status_code=409, detail="Session must be in 'voting' status to finalize")

    new_runoff: dict[int, Optional[list[int]]] = {1: None, 2: None}

    for slot in (1, 2):
        # Skip slots that already have a winner
        existing_winner = session.winner_slot1_id if slot == 1 else session.winner_slot2_id
        if existing_winner is not None:
            continue

        # Determine candidate movie IDs: runoff subset or full slot
        runoff_raw = session.runoff_slot1_ids if slot == 1 else session.runoff_slot2_ids
        if runoff_raw:
            candidate_ids = json.loads(runoff_raw)
        else:
            candidate_ids = [
                r[0] for r in (
                    await db.execute(
                        select(Movie.id)
                        .where(Movie.session_id == session_id)
                        .where(Movie.slot == slot)
                    )
                ).all()
            ]

        if not candidate_ids:
            continue

        vote_rows = (
            await db.execute(
                select(Vote.movie_id, func.count(Vote.id).label("cnt"))
                .where(Vote.session_id == session_id)
                .where(Vote.movie_id.in_(candidate_ids))
                .group_by(Vote.movie_id)
                .order_by(func.count(Vote.id).desc())
            )
        ).all()

        winner, ties = _find_slot_result(vote_rows, candidate_ids)

        if winner is not None:
            if slot == 1:
                session.winner_slot1_id = winner
            else:
                session.winner_slot2_id = winner
            new_runoff[slot] = None
        else:
            new_runoff[slot] = ties
            # Clear votes for tied movies so users vote again
            if ties:
                await db.execute(
                    delete(Vote)
                    .where(Vote.session_id == session_id)
                    .where(Vote.movie_id.in_(ties))
                )

    session.runoff_slot1_ids = json.dumps(new_runoff[1]) if new_runoff[1] else None
    session.runoff_slot2_ids = json.dumps(new_runoff[2]) if new_runoff[2] else None

    # Determine if all resolvable slots now have winners
    has_runoff = bool(new_runoff[1] or new_runoff[2])
    result_status = STATUS_VOTING

    if not has_runoff:
        rating_status = (
            await db.execute(select(SessionStatus).where(SessionStatus.code == STATUS_RATING))
        ).scalar_one()
        session.status_id = rating_status.id
        result_status = STATUS_RATING

    await db.commit()
    await db.refresh(session)

    if result_status == STATUS_RATING:
        winner_titles: dict[int, str] = {}
        for slot, movie_id in {1: session.winner_slot1_id, 2: session.winner_slot2_id}.items():
            if movie_id:
                m = (await db.execute(select(Movie).where(Movie.id == movie_id))).scalar_one_or_none()
                if m:
                    winner_titles[slot] = m.title
        await notify_voting_finalized(winner_titles=winner_titles)

    return {
        "winner_slot1_id": session.winner_slot1_id,
        "winner_slot2_id": session.winner_slot2_id,
        "runoff_slot1_ids": new_runoff[1],
        "runoff_slot2_ids": new_runoff[2],
        "status": result_status,
    }
