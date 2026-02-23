from typing import Literal, Optional

from pydantic import BaseModel


class SuggestResult(BaseModel):
    kinopoisk_id: str
    title: str
    year: Optional[int]
    year_end: Optional[int] = None
    type: Literal['film', 'serial']
    poster_url: Optional[str]
    kp_rating: Optional[float]


class MovieFullResponse(BaseModel):
    kinopoisk_id: str
    kinopoisk_url: str
    title: str
    year: Optional[int]
    year_end: Optional[int] = None
    type: Literal['film', 'serial']
    genres: Optional[str]
    description: Optional[str]
    poster_url: Optional[str]
    kinopoisk_rating: Optional[float]
    trailer_url: Optional[str]


class KinopoiskParseRequest(BaseModel):
    url: str
