from typing import List, Optional

from pydantic import BaseModel

from api.schemas.movie import MovieResponse


class LeaderboardEntry(BaseModel):
    movie: MovieResponse
    vote_count: int
    rating_count: int


class LeaderboardResponse(BaseModel):
    items: List[LeaderboardEntry]
    total: int
    page: int
    pages: int


class ClubStats(BaseModel):
    total_movies: int
    total_sessions: int
    total_users: int
    avg_club_rating: Optional[float]
