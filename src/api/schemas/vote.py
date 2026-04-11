from datetime import datetime

from pydantic import BaseModel, Field


class VoteResponse(BaseModel):
    id: int
    session_id: int
    movie_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VoteRequest(BaseModel):
    session_id: int
    movie_ids: list[int] = Field(min_length=1)  # all selected movies in one slot (replaces previous votes)
    slot: int = Field(ge=1, le=2)


class VoterInfo(BaseModel):
    telegram_id: int
    first_name: str | None
    last_name: str | None
    username: str | None


class MovieVoteResult(BaseModel):
    movie_id: int
    vote_count: int
    voters: list[VoterInfo]


class VoteResultsResponse(BaseModel):
    session_id: int
    results: list[MovieVoteResult]
