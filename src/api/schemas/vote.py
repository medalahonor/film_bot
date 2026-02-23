from datetime import datetime

from pydantic import BaseModel


class VoteResponse(BaseModel):
    id: int
    session_id: int
    movie_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VoteRequest(BaseModel):
    session_id: int
    movie_ids: list[int]  # all selected movies in one slot (replaces previous votes)
    slot: int


class MovieVoteResult(BaseModel):
    movie_id: int
    vote_count: int


class VoteResultsResponse(BaseModel):
    session_id: int
    results: list[MovieVoteResult]
