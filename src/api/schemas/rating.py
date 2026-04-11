from datetime import datetime

from pydantic import BaseModel, Field


class RatingResponse(BaseModel):
    id: int
    session_id: int
    movie_id: int
    rating: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingRequest(BaseModel):
    session_id: int
    movie_id: int
    rating: int = Field(ge=1, le=10)


class RaterInfo(BaseModel):
    telegram_id: int
    first_name: str | None
    last_name: str | None
    username: str | None
    rating: int
    created_at: datetime


class OpenMovieRatings(BaseModel):
    movie_id: int
    club_rating: float | None
    raters: list[RaterInfo]


class OpenRatingsResponse(BaseModel):
    session_id: int
    results: list[OpenMovieRatings]
