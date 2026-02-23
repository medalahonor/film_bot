"""Kinopoisk API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List

from api.dependencies import get_current_user
from api.schemas.kinopoisk import KinopoiskParseRequest, MovieFullResponse, SuggestResult
from bot.database.models import User
from bot.services.kinopoisk import (
    KinopoiskParserError,
    get_movie_by_id,
    parse_movie_data,
    suggest_search,
)

router = APIRouter(prefix="/api/kinopoisk", tags=["kinopoisk"])


def _to_movie_full(data: dict) -> MovieFullResponse:
    return MovieFullResponse(
        kinopoisk_id=data['kinopoisk_id'],
        kinopoisk_url=data.get('kinopoisk_url', f"https://www.kinopoisk.ru/film/{data['kinopoisk_id']}/"),
        title=data['title'],
        year=data.get('year'),
        year_end=data.get('year_end'),
        type=data.get('type', 'film'),
        genres=data.get('genres'),
        description=data.get('description'),
        poster_url=data.get('poster_url'),
        kinopoisk_rating=data.get('kinopoisk_rating'),
        trailer_url=data.get('trailer_url'),
    )


@router.get("/suggest", response_model=List[SuggestResult])
async def kinopoisk_suggest(
    query: str = Query(..., min_length=1),
    _user: User = Depends(get_current_user),
) -> List[SuggestResult]:
    try:
        results = await suggest_search(query, limit=3)
    except KinopoiskParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return [SuggestResult(**r) for r in results]


@router.get("/movie/{kinopoisk_id}", response_model=MovieFullResponse)
async def kinopoisk_movie_by_id(
    kinopoisk_id: str,
    _user: User = Depends(get_current_user),
) -> MovieFullResponse:
    try:
        data = await get_movie_by_id(kinopoisk_id)
    except KinopoiskParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return _to_movie_full(data)


@router.post("/parse", response_model=MovieFullResponse)
async def kinopoisk_parse(
    body: KinopoiskParseRequest,
    _user: User = Depends(get_current_user),
) -> MovieFullResponse:
    try:
        data = await parse_movie_data(body.url)
    except KinopoiskParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_movie_full(data)
