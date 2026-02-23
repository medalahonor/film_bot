from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProposeMovieRequest(BaseModel):
    session_id: int
    slot: int = Field(ge=1, le=2)
    kinopoisk_id: str
    kinopoisk_url: str
    title: str
    year: Optional[int] = None
    year_end: Optional[int] = None
    type: Literal['film', 'serial']
    genres: Optional[str] = None
    description: Optional[str] = None
    poster_url: Optional[str] = None
    kinopoisk_rating: Optional[float] = None
    trailer_url: Optional[str] = None


class UpdateClubRatingRequest(BaseModel):
    club_rating: float = Field(ge=0, le=10)


class ReplaceMovieRequest(BaseModel):
    slot: int = Field(ge=1, le=2)
    kinopoisk_id: str
    kinopoisk_url: str
    title: str
    year: Optional[int] = None
    year_end: Optional[int] = None
    type: Literal['film', 'serial']
    genres: Optional[str] = None
    description: Optional[str] = None
    poster_url: Optional[str] = None
    kinopoisk_rating: Optional[float] = None
    trailer_url: Optional[str] = None


class MovieResponse(BaseModel):
    id: int
    session_id: int
    slot: int
    kinopoisk_id: str
    kinopoisk_url: str
    title: str
    year: Optional[int]
    year_end: Optional[int] = None  # completed serials only
    type: Literal['film', 'serial']
    genres: Optional[str]
    description: Optional[str]
    poster_url: Optional[str]
    kinopoisk_rating: Optional[float]
    club_rating: Optional[float]
    trailer_url: Optional[str]
    proposer_username: Optional[str]
    proposer_first_name: Optional[str]
    proposer_telegram_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
