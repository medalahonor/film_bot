"""Kinopoisk parser service.

Uses Kinopoisk GraphQL API (graphql.kinopoisk.ru) for fast, structured data retrieval.
"""
import json
import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import aiohttp

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

from api.services._graphql_queries import (
    FILM_BASE_INFO_QUERY,
    FILM_BASE_INFO_VARIABLES_TEMPLATE,
    SUGGEST_SEARCH_QUERY,
    SUGGEST_SEARCH_URL,
    TV_SERIES_BASE_INFO_QUERY,
    TV_SERIES_BASE_INFO_URL,
    TV_SERIES_BASE_INFO_VARIABLES_TEMPLATE,
)

# Poster size suffix for avatarsUrl
_POSTER_SIZE = "300x450"

# Timeout for HTTP requests (seconds)
_HTTP_TIMEOUT = 15

# __typename values that indicate a serial
_SERIAL_TYPENAMES = ('TvSeries', 'TvShow', 'MiniSeries')

# ── Exceptions ───────────────────────────────────────────────────────────


class KinopoiskParserError(Exception):
    """Exception raised when parsing fails."""


# ── URL helpers ──────────────────────────────────────────────────────────


def extract_kinopoisk_id(url: str) -> Optional[str]:
    """Extract Kinopoisk film/serial ID from URL.

    Supports both /film/<id>/ and /series/<id>/ formats.
    """
    pattern = r'kinopoisk\.ru/(?:film|series)/(\d+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def is_valid_kinopoisk_url(url: str) -> bool:
    """Check if URL is a valid Kinopoisk film or serial URL."""
    try:
        parsed = urlparse(url)
        if 'kinopoisk.ru' not in parsed.netloc:
            return False
        if '/film/' not in parsed.path and '/series/' not in parsed.path:
            return False
        return extract_kinopoisk_id(url) is not None
    except (ValueError, AttributeError):
        return False


# ── GraphQL API ──────────────────────────────────────────────────────────


def _build_poster_url(avatars_url: Optional[str], fallback_url: Optional[str]) -> Optional[str]:
    """Build full poster URL from GraphQL response fields."""
    if avatars_url:
        base = avatars_url.rstrip('/')
        if base.startswith('//'):
            base = 'https:' + base
        return f"{base}/{_POSTER_SIZE}"
    if fallback_url:
        return fallback_url
    return None


def _determine_type(typename: Optional[str]) -> str:
    """Map GraphQL __typename to 'film' or 'serial'."""
    if typename in _SERIAL_TYPENAMES:
        return 'serial'
    return 'film'


def _extract_year_for_serial(film: Dict[str, Any]) -> Optional[int]:
    """Extract start year from releaseYears for serials."""
    release_years = film.get('releaseYears') or []
    if release_years:
        return release_years[0].get('start')
    return None


def _extract_year_end(film: Dict[str, Any]) -> Optional[int]:
    """Extract end year from releaseYears (last element) for serials."""
    release_years = film.get('releaseYears') or []
    if release_years:
        return release_years[-1].get('end')
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

    # Type from __typename
    typename = film.get('__typename')
    content_type = _determine_type(typename)

    # Year: productionYear for films, releaseYears[0].start for serials
    year = film.get("productionYear")
    if year is None and content_type == 'serial':
        year = _extract_year_for_serial(film)

    # Year end (for completed serials)
    year_end = _extract_year_end(film) if content_type == 'serial' else None

    # Genres
    genres_list = film.get("genres") or []
    genre_names = [g["name"] for g in genres_list if g.get("name")]
    genres_str = ", ".join(genre_names) if genre_names else None

    # Description (prefer shortDescription, fallback to synopsis)
    description = film.get("shortDescription") or film.get("synopsis")

    # Poster URL
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
    if content_type == 'serial':
        normalized_url = f"https://www.kinopoisk.ru/series/{kinopoisk_id}/"
    else:
        normalized_url = f"https://www.kinopoisk.ru/film/{kinopoisk_id}/"

    if trailer_id:
        trailer_url = f"https://widgets.kinopoisk.ru/discovery/film/{kinopoisk_id}/trailer/{trailer_id}?noAd=0&hidden=&muted=&loop=0&autoplay=1&from=&extraTrailers=&onlyPlayer=1"
    
    return {
        'kinopoisk_id': kinopoisk_id,
        'kinopoisk_url': normalized_url,
        'title': title,
        'year': year,
        'year_end': year_end,
        'type': content_type,
        'genres': genres_str,
        'description': description,
        'poster_url': poster_url,
        'kinopoisk_rating': rating,
        'trailer_url': trailer_url,
    }


def _parse_suggest_movie(movie: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a single movie object from SuggestSearch response."""
    typename = movie.get('__typename')
    content_type = _determine_type(typename)

    title_data = movie.get('title') or {}
    title = title_data.get('russian') or title_data.get('original') or ''

    kinopoisk_id = str(movie.get('id', ''))

    # Year
    year: Optional[int] = movie.get('productionYear')
    year_end: Optional[int] = None
    if content_type == 'serial':
        year = _extract_year_for_serial(movie)
        year_end = _extract_year_end(movie)

    # Rating
    kp_rating: Optional[float] = None
    rating_value = (movie.get('rating') or {}).get('kinopoisk', {}).get('value')
    if rating_value is not None:
        try:
            kp_rating = float(rating_value)
        except (ValueError, TypeError):
            pass

    # Poster — новый запрос возвращает hdVertical/kpVertical (алиасы)
    gallery = movie.get('gallery') or {}
    posters = gallery.get('posters') or {}
    vertical = posters.get('hdVertical') or posters.get('kpVertical') or posters.get('vertical') or {}
    poster_url = _build_poster_url(
        vertical.get('avatarsUrl'),
        vertical.get('fallbackUrl'),
    )

    return {
        'kinopoisk_id': kinopoisk_id,
        'title': title,
        'year': year,
        'year_end': year_end,
        'type': content_type,
        'poster_url': poster_url,
        'kp_rating': kp_rating,
    }


def _parse_tvseries_graphql_response(data: Dict[str, Any], kinopoisk_id: str) -> Dict[str, Any]:
    """Convert GraphQL TvSeries response to our standard movie dict.

    Raises:
        KinopoiskParserError: If essential data (title) is missing.
    """
    tv = data.get("tvSeries")
    if not tv:
        raise KinopoiskParserError("Сериал не найден на Кинопоиске")

    title_data = tv.get("title") or {}
    title = title_data.get("russian") or title_data.get("original")
    if not title:
        raise KinopoiskParserError("Не удалось извлечь название сериала")

    year = _extract_year_for_serial(tv)
    year_end = _extract_year_end(tv)

    genres_list = tv.get("genres") or []
    genre_names = [g["name"] for g in genres_list if g.get("name")]
    genres_str = ", ".join(genre_names) if genre_names else None

    description = tv.get("shortDescription") or tv.get("synopsis")

    gallery = tv.get("gallery") or {}
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

    rating = None
    rating_data = tv.get("rating") or {}
    kp_rating = rating_data.get("kinopoisk") or {}
    rating_value = kp_rating.get("value")
    if rating_value is not None:
        try:
            rating = float(rating_value)
        except (ValueError, TypeError):
            pass

    trailer_url = None
    main_trailer = tv.get("mainTrailer") or {}
    trailer_id = main_trailer.get("id")
    if trailer_id:
        # trailer_url = f"https://www.kinopoisk.ru/film/{kinopoisk_id}/video/{trailer_id}/"
        trailer_url = f"https://widgets.kinopoisk.ru/discovery/film/{kinopoisk_id}/trailer/{trailer_id}?noAd=0&hidden=&muted=&loop=0&autoplay=1&from=&extraTrailers=&onlyPlayer=1"
    return {
        'kinopoisk_id': kinopoisk_id,
        'kinopoisk_url': f"https://www.kinopoisk.ru/series/{kinopoisk_id}/",
        'title': title,
        'year': year,
        'year_end': year_end,
        'type': 'serial',
        'genres': genres_str,
        'description': description,
        'poster_url': poster_url,
        'kinopoisk_rating': rating,
        'trailer_url': trailer_url,
    }


async def _fetch_tvseries_via_graphql(kinopoisk_id: str) -> Dict[str, Any]:
    """Fetch TvSeries data from Kinopoisk GraphQL API."""
    tv_id = int(kinopoisk_id)
    variables = {**TV_SERIES_BASE_INFO_VARIABLES_TEMPLATE, "tvSeriesId": tv_id}
    payload = {
        "operationName": "TvSeriesBaseInfo",
        "variables": variables,
        "query": TV_SERIES_BASE_INFO_QUERY,
    }

    try:
        async with aiohttp.ClientSession(headers=GRAPHQL_HEADERS) as session:
            async with session.post(
                TV_SERIES_BASE_INFO_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT),
            ) as response:
                if response.status != 200:
                    body_text = (await response.text())[:300]
                    logger.error("TvSeriesBaseInfo HTTP %d: %s", response.status, body_text)
                    raise KinopoiskParserError(
                        f"Кинопоиск GraphQL вернул HTTP {response.status}"
                    )

                body = await response.json()

                if "errors" in body and not body.get("data"):
                    errors_text = json.dumps(body["errors"], ensure_ascii=False)[:300]
                    logger.error("GraphQL errors: %s", errors_text)
                    raise KinopoiskParserError("Ошибка GraphQL Кинопоиска")

                data = body.get("data")
                if not data:
                    raise KinopoiskParserError("Пустой ответ от GraphQL Кинопоиска")

                return _parse_tvseries_graphql_response(data, kinopoisk_id)

    except KinopoiskParserError:
        raise
    except Exception as exc:
        logger.error("TvSeriesBaseInfo request failed: %s", exc)
        raise KinopoiskParserError(
            "Не удалось получить данные сериала с Кинопоиска"
        ) from exc


async def _fetch_movie_via_graphql(kinopoisk_id: str) -> Dict[str, Any]:
    """Fetch movie data from Kinopoisk GraphQL API."""
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
                    raise KinopoiskParserError("Ошибка GraphQL Кинопоиска")

                data = body.get("data")
                if not data:
                    raise KinopoiskParserError("Пустой ответ от GraphQL Кинопоиска")

                return _parse_graphql_response(data, kinopoisk_id)

    except KinopoiskParserError:
        raise
    except Exception as exc:
        logger.error("GraphQL request failed: %s", exc)
        raise KinopoiskParserError(
            "Не удалось получить данные фильма с Кинопоиска"
        ) from exc


# ── Public API ───────────────────────────────────────────────────────────


async def parse_movie_data(url: str) -> Dict[str, Any]:
    """Parse movie/serial data from Kinopoisk URL via GraphQL API."""
    if not is_valid_kinopoisk_url(url):
        raise KinopoiskParserError("Неверный URL Кинопоиска")

    kinopoisk_id = extract_kinopoisk_id(url)
    if not kinopoisk_id:
        raise KinopoiskParserError("Не удалось извлечь ID фильма из URL")

    if '/series/' in url:
        result = await _fetch_tvseries_via_graphql(kinopoisk_id)
    else:
        result = await _fetch_movie_via_graphql(kinopoisk_id)
    logger.info("Movie '%s' fetched via GraphQL", result.get('title'))
    return result


async def get_movie_by_id(kinopoisk_id: str) -> Dict[str, Any]:
    """Fetch full movie data by Kinopoisk ID (without URL)."""
    result = await _fetch_movie_via_graphql(kinopoisk_id)
    logger.info("Movie '%s' fetched by ID %s", result.get('title'), kinopoisk_id)
    return result


async def get_series_by_id(kinopoisk_id: str) -> Dict[str, Any]:
    """Fetch full TvSeries data by Kinopoisk ID (without URL)."""
    result = await _fetch_tvseries_via_graphql(kinopoisk_id)
    logger.info("Series '%s' fetched by ID %s", result.get('title'), kinopoisk_id)
    return result


async def suggest_search(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search movies and serials via SuggestSearch GraphQL.

    Returns list of dicts: [{kinopoisk_id, title, year, year_end, poster_url, kp_rating, type}]
    """
    payload = {
        "operationName": "SuggestSearch",
        "variables": {"keyword": query, "yandexCityId": 100, "limit": limit},
        "query": SUGGEST_SEARCH_QUERY,
    }

    try:
        async with aiohttp.ClientSession(headers=GRAPHQL_HEADERS) as session:
            async with session.post(
                SUGGEST_SEARCH_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT),
            ) as response:
                if response.status != 200:
                    body_text = (await response.text())[:300]
                    logger.error("SuggestSearch HTTP %d: %s", response.status, body_text)
                    raise KinopoiskParserError(f"Кинопоиск вернул HTTP {response.status}")

                body = await response.json()
                top = body.get("data", {}).get("suggest", {}).get("top", {})
                top_result_raw = (top.get("topResult") or {}).get("global")
                movies_raw = top.get("movies", [])

                _movie_typenames = ('Film', 'TvSeries', 'TvShow', 'MiniSeries')
                results: List[Dict[str, Any]] = []
                seen_ids: set = set()

                if (
                    top_result_raw
                    and top_result_raw.get("__typename") in _movie_typenames
                    and top_result_raw.get("id")
                ):
                    parsed = _parse_suggest_movie(top_result_raw)
                    results.append(parsed)
                    seen_ids.add(parsed["kinopoisk_id"])

                for item in movies_raw:
                    if len(results) >= limit:
                        break
                    movie = item.get("movie") if isinstance(item, dict) else item
                    if not movie or not movie.get("id"):
                        continue
                    kid = str(movie["id"])
                    if kid in seen_ids:
                        continue
                    results.append(_parse_suggest_movie(movie))
                    seen_ids.add(kid)

                return results

    except KinopoiskParserError:
        raise
    except Exception as exc:
        logger.error("SuggestSearch failed: %s", exc)
        raise KinopoiskParserError("Поиск на Кинопоиске недоступен") from exc


async def format_movie_info(movie_data: Dict[str, Any]) -> str:
    """Format movie data for Telegram message display."""
    title = movie_data.get('title', 'Без названия')
    year = movie_data.get('year')
    genres = movie_data.get('genres', '')
    rating = movie_data.get('kinopoisk_rating')
    description = movie_data.get('description')
    trailer_url = movie_data.get('trailer_url')
    content_type = movie_data.get('type', 'film')

    type_emoji = '📺' if content_type == 'serial' else '🎬'
    header_parts = [f"{type_emoji} <b>{title}</b>"]
    if year:
        year_end = movie_data.get('year_end')
        if year_end and year_end != year:
            header_parts.append(f"({year}–{year_end})")
        else:
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
