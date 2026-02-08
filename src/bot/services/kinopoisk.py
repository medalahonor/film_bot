"""Kinopoisk parser service.

Uses Kinopoisk GraphQL API (graphql.kinopoisk.ru) for fast, structured data retrieval.
"""
import json
import re
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

GRAPHQL_URL = "https://graphql.kinopoisk.ru/graphql/?operationName=FilmBaseInfo"

GRAPHQL_HEADERS = {
    'Accept': '*/*',
    'Accept-Language': 'ru,en;q=0.9',
    'Content-Type': 'application/json',
    'Origin': 'https://www.kinopoisk.ru',
    'Referer': 'https://www.kinopoisk.ru/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'Service-Id': '25',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'X-Preferred-Language': 'ru',
}

from bot.services._graphql_queries import (
    FILM_BASE_INFO_QUERY,
    FILM_BASE_INFO_VARIABLES_TEMPLATE,
)

# Poster size suffix for avatarsUrl
_POSTER_SIZE = "300x450"

# Timeout for HTTP requests (seconds)
_HTTP_TIMEOUT = 15

# ── Exceptions ───────────────────────────────────────────────────────────


class KinopoiskParserError(Exception):
    """Exception raised when parsing fails."""


# ── URL helpers ──────────────────────────────────────────────────────────


def extract_kinopoisk_id(url: str) -> Optional[str]:
    """Extract Kinopoisk film ID from URL.

    Examples:
        https://www.kinopoisk.ru/film/301/ -> 301
        https://www.kinopoisk.ru/film/301/cast/ -> 301
    """
    pattern = r'kinopoisk\.ru/film/(\d+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def is_valid_kinopoisk_url(url: str) -> bool:
    """Check if URL is a valid Kinopoisk film URL."""
    try:
        parsed = urlparse(url)
        if 'kinopoisk.ru' not in parsed.netloc:
            return False
        if '/film/' not in parsed.path:
            return False
        return extract_kinopoisk_id(url) is not None
    except (ValueError, AttributeError):
        return False


# ── GraphQL API ──────────────────────────────────────────────────────────


def _build_poster_url(avatars_url: Optional[str], fallback_url: Optional[str]) -> Optional[str]:
    """Build full poster URL from GraphQL response fields.

    avatarsUrl is a base like //avatars.mds.yandex.net/get-kinopoisk-image/...
    We prepend https: and append the size suffix.
    fallbackUrl is used as-is if avatarsUrl is missing.
    """
    if avatars_url:
        base = avatars_url.rstrip('/')
        if base.startswith('//'):
            base = 'https:' + base
        return f"{base}/{_POSTER_SIZE}"
    if fallback_url:
        return fallback_url
    return None


def _parse_graphql_response(data: Dict[str, Any], kinopoisk_id: str) -> Dict[str, Any]:
    """Convert GraphQL film response to our standard movie dict.

    Raises:
        KinopoiskParserError: If essential data (title) is missing.
    """
    film = data.get("film")
    if not film:
        raise KinopoiskParserError("Фильм не найден на Кинопоиске")

    title_data = film.get("title") or {}
    title = title_data.get("russian") or title_data.get("original")
    if not title:
        raise KinopoiskParserError("Не удалось извлечь название фильма")

    # Year
    year = film.get("productionYear")

    # Genres
    genres_list = film.get("genres") or []
    genre_names = [g["name"] for g in genres_list if g.get("name")]
    genres_str = ", ".join(genre_names) if genre_names else None

    # Description (prefer shortDescription, fallback to synopsis)
    description = film.get("shortDescription") or film.get("synopsis")

    # Poster URL (full query returns kpVertical / marketingVertical aliases)
    gallery = film.get("gallery") or {}
    posters = gallery.get("posters") or {}
    vertical = (
        posters.get("marketingVertical")
        or posters.get("kpVertical")
        or posters.get("vertical")
        or {}
    )
    poster_url = _build_poster_url(
        vertical.get("avatarsUrl"),
        vertical.get("fallbackUrl"),
    )

    # Rating
    rating = None
    rating_data = film.get("rating") or {}
    kp_rating = rating_data.get("kinopoisk") or {}
    rating_value = kp_rating.get("value")
    if rating_value is not None:
        try:
            rating = float(rating_value)
        except (ValueError, TypeError):
            pass

    # Trailer URL from mainTrailer.id
    trailer_url = None
    main_trailer = film.get("mainTrailer") or {}
    trailer_id = main_trailer.get("id")
    if trailer_id:
        trailer_url = f"https://www.kinopoisk.ru/film/{kinopoisk_id}/video/{trailer_id}/"

    normalized_url = f"https://www.kinopoisk.ru/film/{kinopoisk_id}/"

    return {
        'kinopoisk_id': kinopoisk_id,
        'kinopoisk_url': normalized_url,
        'title': title,
        'year': year,
        'genres': genres_str,
        'description': description,
        'poster_url': poster_url,
        'kinopoisk_rating': rating,
        'trailer_url': trailer_url,
    }


async def _fetch_movie_via_graphql(kinopoisk_id: str) -> Dict[str, Any]:
    """Fetch movie data from Kinopoisk GraphQL API.

    Raises:
        KinopoiskParserError: On any failure.
    """
    film_id = int(kinopoisk_id)
    variables = {**FILM_BASE_INFO_VARIABLES_TEMPLATE, "filmId": film_id}
    payload = {
        "operationName": "FilmBaseInfo",
        "variables": variables,
        "query": FILM_BASE_INFO_QUERY,
    }

    try:
        async with aiohttp.ClientSession(headers=GRAPHQL_HEADERS) as session:
            async with session.post(
                GRAPHQL_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT),
            ) as response:
                if response.status != 200:
                    body_text = (await response.text())[:300]
                    logger.error("GraphQL HTTP %d: %s", response.status, body_text)
                    raise KinopoiskParserError(
                        f"Кинопоиск GraphQL вернул HTTP {response.status}"
                    )

                body = await response.json()

                if "errors" in body and not body.get("data"):
                    errors_text = json.dumps(body["errors"], ensure_ascii=False)[:300]
                    logger.error("GraphQL errors: %s", errors_text)
                    raise KinopoiskParserError(
                        "Ошибка GraphQL Кинопоиска"
                    )

                data = body.get("data")
                if not data:
                    raise KinopoiskParserError(
                        "Пустой ответ от GraphQL Кинопоиска"
                    )

                result = _parse_graphql_response(data, kinopoisk_id)
                return result

    except KinopoiskParserError:
        raise
    except Exception as exc:
        logger.error("GraphQL request failed: %s", exc)
        raise KinopoiskParserError(
            "Не удалось получить данные фильма с Кинопоиска"
        ) from exc


# ── Public API ───────────────────────────────────────────────────────────


async def parse_movie_data(url: str) -> Dict[str, Any]:
    """Parse movie data from Kinopoisk URL via GraphQL API.

    Returns:
        Dictionary with movie data

    Raises:
        KinopoiskParserError: If parsing fails
    """
    if not is_valid_kinopoisk_url(url):
        raise KinopoiskParserError("Неверный URL Кинопоиска")

    kinopoisk_id = extract_kinopoisk_id(url)
    if not kinopoisk_id:
        raise KinopoiskParserError("Не удалось извлечь ID фильма из URL")

    result = await _fetch_movie_via_graphql(kinopoisk_id)
    logger.info("Movie '%s' fetched via GraphQL", result.get('title'))
    return result


async def format_movie_info(movie_data: Dict[str, Any]) -> str:
    """Format movie data for Telegram message display."""
    title = movie_data.get('title', 'Без названия')
    year = movie_data.get('year')
    genres = movie_data.get('genres', '')
    rating = movie_data.get('kinopoisk_rating')
    description = movie_data.get('description')
    trailer_url = movie_data.get('trailer_url')

    header_parts = [f"🎬 <b>{title}</b>"]
    if year:
        header_parts.append(f"({year})")

    lines = [' '.join(header_parts)]

    if genres:
        lines.append(genres)

    if rating:
        lines.append(f"⭐️ {rating} на Кинопоиске")

    if description:
        lines.append(f"\n📝 {description}")

    if trailer_url:
        lines.append(f"\n🎥 <a href=\"{trailer_url}\">Смотреть трейлер</a>")

    return '\n'.join(lines)
