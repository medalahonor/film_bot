"""Leaderboard handlers."""
import logging
import math
from typing import List, Tuple, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Session, Movie, Rating, User
from bot.database.session import AsyncSessionLocal
from bot.database.status_manager import get_status_by_code, STATUS_COMPLETED
from bot.database.repositories import (
    resolve_telegram_group_id,
    get_group_by_telegram_id,
)
from bot.formatters import format_year_suffix, format_user_display_name
from bot.keyboards import (
    get_leaderboard_pagination_keyboard, get_cancel_keyboard,
    get_main_menu_keyboard,
    BTN_LEADERBOARD, BTN_SEARCH, BTN_STATS,
)
from bot.utils import try_delete_message, finish_flow

logger = logging.getLogger(__name__)

router = Router()

MOVIES_PER_PAGE = 10


class LeaderboardState(StatesGroup):
    """States for leaderboard."""
    waiting_for_search = State()


# ── Data layer ───────────────────────────────────────────────────────────


async def _resolve_group(
    db: AsyncSession,
    chat_id: int,
    chat_type: str,
):
    """Resolve the internal group from a chat. Returns (group, error_msg)."""
    group_telegram_id = resolve_telegram_group_id(chat_id, chat_type)
    group = await get_group_by_telegram_id(db, group_telegram_id)
    return group


async def _query_winner_movies(
    db: AsyncSession,
    group_id: int,
    page: int = 1,
    search_query: Optional[str] = None,
) -> Tuple[List[dict], int, int]:
    """Query winner movies with ratings, pagination, and optional search.

    Returns:
        (movies_data, total_pages, total_movies)
    """
    completed_status = await get_status_by_code(db, STATUS_COMPLETED)
    if not completed_status:
        return [], 0, 0

    session_ids = await _get_completed_session_ids(db, group_id, completed_status.id)
    if not session_ids:
        return [], 0, 0

    query = _build_leaderboard_query(session_ids, search_query)

    total_movies = await _count_query_results(db, query)
    if total_movies == 0:
        return [], 0, 0

    total_pages = math.ceil(total_movies / MOVIES_PER_PAGE)

    query = query.order_by(Movie.club_rating.desc().nullslast())
    offset = (page - 1) * MOVIES_PER_PAGE
    query = query.offset(offset).limit(MOVIES_PER_PAGE)

    result = await db.execute(query)
    rows = result.all()

    movies_data = await _enrich_with_proposers(db, rows, offset)

    return movies_data, total_pages, total_movies


async def _get_completed_session_ids(
    db: AsyncSession,
    group_id: int,
    completed_status_id: int,
) -> List[int]:
    """Get IDs of all completed sessions for a group."""
    result = await db.execute(
        select(Session.id)
        .where(Session.group_id == group_id)
        .where(Session.status_id == completed_status_id)
    )
    return [row[0] for row in result.all()]


def _build_leaderboard_query(session_ids: List[int], search_query: Optional[str] = None):
    """Build the base leaderboard query with optional search filter."""
    query = (
        select(
            Movie,
            func.count(Rating.id).label('rating_count'),
            Movie.club_rating.label('avg_rating'),
        )
        .join(Session, Movie.session_id == Session.id)
        .outerjoin(Rating, Movie.id == Rating.movie_id)
        .where(Session.id.in_(session_ids))
        .where(
            or_(
                Movie.id == Session.winner_slot1_id,
                Movie.id == Session.winner_slot2_id,
            )
        )
        .group_by(Movie.id)
    )

    if search_query:
        search_pattern = f"%{search_query.lower()}%"
        query = query.where(func.lower(Movie.title).like(search_pattern))

    return query


async def _count_query_results(db: AsyncSession, query) -> int:
    """Count the total number of results for a query."""
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    return result.scalar()


async def _enrich_with_proposers(
    db: AsyncSession,
    rows: list,
    offset: int,
) -> List[dict]:
    """Enrich movie rows with proposer names and ranking."""
    movies_data = []
    for idx, row in enumerate(rows, start=offset + 1):
        movie, rating_count, avg_rating = row

        result_user = await db.execute(
            select(User).where(User.id == movie.user_id)
        )
        proposer = result_user.scalar_one()
        proposer_name = format_user_display_name(
            proposer.username, proposer.first_name,
        )

        movies_data.append({
            'rank': idx,
            'movie': movie,
            'rating_count': rating_count or 0,
            'avg_rating': round(float(avg_rating), 2) if avg_rating else 0.0,
            'proposer_name': proposer_name,
        })

    return movies_data


# ── Formatting ───────────────────────────────────────────────────────────


def format_leaderboard_message(
    movies_data: List[dict],
    page: int,
    total_pages: int,
    total_movies: int,
    search_query: Optional[str] = None,
) -> str:
    """Format leaderboard message."""
    if search_query:
        response = f"🔍 <b>Результаты поиска: \"{search_query}\"</b>\n\n"
    else:
        response = f"🏆 <b>ТАБЛИЦА ЛИДЕРОВ КИНОКЛУБА</b> (Страница {page}/{total_pages})\n\n"

    if not movies_data:
        return response + "Нет фильмов для отображения."

    for data in movies_data:
        rank = data['rank']
        movie = data['movie']
        rating_count = data['rating_count']
        avg_rating = data['avg_rating']
        proposer_name = data['proposer_name']

        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")
        year_str = format_year_suffix(movie.year)

        response += f"{medal} <b>{movie.title}</b>{year_str}\n"

        if rating_count > 0:
            response += f"   ⭐ {avg_rating:.2f} ({rating_count} оценок)\n"
        elif avg_rating and avg_rating > 0:
            response += f"   ⭐ {avg_rating:.2f}\n"
        else:
            response += "   Нет оценок\n"

        response += f"   Предложил: {proposer_name}\n\n"

    if not search_query:
        response += f"📊 Всего просмотрено: {total_movies} фильмов"
    else:
        response += f"\nНайдено: {len(movies_data)} фильм(ов)"

    return response


# ── Handlers ─────────────────────────────────────────────────────────────


@router.message(F.text == BTN_LEADERBOARD)
async def show_leaderboard(message: Message, state: FSMContext) -> None:
    """Show leaderboard with top rated movies via reply keyboard button."""
    await state.clear()
    logger.info("User %s requested leaderboard", message.from_user.id)
    async with AsyncSessionLocal() as db:
        try:
            group = await _resolve_group(db, message.chat.id, message.chat.type)
            if not group:
                await message.answer(
                    "ℹ️ Группа не найдена. Сначала создайте сессию в группе."
                )
                return

            movies_data, total_pages, total_movies = await _query_winner_movies(
                db, group.id, page=1,
            )

            if not movies_data:
                await message.answer(
                    "ℹ️ Таблица лидеров пуста.\n\n"
                    "Завершите хотя бы одну сессию с рейтингами."
                )
                return

            text = format_leaderboard_message(
                movies_data, page=1,
                total_pages=total_pages,
                total_movies=total_movies,
            )

            if total_pages > 1:
                keyboard = get_leaderboard_pagination_keyboard(1, total_pages)
                await message.answer(text, reply_markup=keyboard)
            else:
                await message.answer(text)

        except Exception as e:
            logger.exception("Error showing leaderboard: %s", e)
            await message.answer(
                "❌ Произошла ошибка при получении таблицы лидеров."
            )


@router.callback_query(F.data.startswith("lb_page:"))
async def handle_leaderboard_page(callback: CallbackQuery) -> None:
    """Handle leaderboard pagination."""
    try:
        page = int(callback.data.split(":")[1])
        logger.info("User %s requested leaderboard page %s", callback.from_user.id, page)

        async with AsyncSessionLocal() as db:
            group = await _resolve_group(
                db, callback.message.chat.id, callback.message.chat.type,
            )
            if not group:
                await callback.answer("❌ Группа не найдена")
                return

            movies_data, total_pages, total_movies = await _query_winner_movies(
                db, group.id, page=page,
            )

            text = format_leaderboard_message(
                movies_data, page=page,
                total_pages=total_pages,
                total_movies=total_movies,
            )

            keyboard = get_leaderboard_pagination_keyboard(page, total_pages)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()

    except Exception as e:
        logger.exception("Error handling pagination: %s", e)
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(F.data == "lb_search")
async def handle_leaderboard_search_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle search button press (inline button in leaderboard)."""
    logger.info("User %s pressed leaderboard search button", callback.from_user.id)
    await state.set_state(LeaderboardState.waiting_for_search)

    bot_msg = await callback.message.answer(
        "🔍 Введите название фильма для поиска:",
        reply_markup=get_cancel_keyboard(),
    )
    await state.update_data(bot_message_id=bot_msg.message_id)
    await callback.answer()


async def perform_search(message: Message, query: str) -> None:
    """Perform movie search and send results."""
    logger.info("User %s searching movies: '%s'", message.from_user.id, query)
    async with AsyncSessionLocal() as db:
        try:
            group = await _resolve_group(db, message.chat.id, message.chat.type)
            if not group:
                await message.answer(
                    "ℹ️ Группа не найдена.",
                    reply_markup=get_main_menu_keyboard(),
                )
                return

            movies_data, _, _ = await _query_winner_movies(
                db, group.id, page=1, search_query=query,
            )

            if not movies_data:
                await message.answer(
                    f"🔍 По запросу \"<b>{query}</b>\" ничего не найдено.",
                    reply_markup=get_main_menu_keyboard(),
                )
                return

            response = _format_search_results(query, movies_data)
            await message.answer(response, reply_markup=get_main_menu_keyboard())

        except Exception as e:
            logger.exception("Error searching movies: %s", e)
            await message.answer(
                "❌ Произошла ошибка при поиске.",
                reply_markup=get_main_menu_keyboard(),
            )


@router.message(F.text == BTN_SEARCH)
async def search_button(message: Message, state: FSMContext) -> None:
    """Start search via button — ask for query."""
    logger.info("User %s started search flow", message.from_user.id)
    await state.clear()
    await try_delete_message(message)

    await state.set_state(LeaderboardState.waiting_for_search)

    bot_msg = await message.answer(
        "🔍 Введите название фильма для поиска:",
        reply_markup=get_cancel_keyboard(),
    )
    await state.update_data(bot_message_id=bot_msg.message_id)


@router.message(LeaderboardState.waiting_for_search)
async def search_from_state(message: Message, state: FSMContext) -> None:
    """Handle search query text from FSM state."""
    query = message.text.strip() if message.text else ""

    await try_delete_message(message)
    await finish_flow(message, state)

    if not query:
        await message.answer(
            "⚠️ Пустой запрос. Попробуйте ещё раз.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    await perform_search(message, query)


@router.message(F.text == BTN_STATS)
async def show_stats(message: Message, state: FSMContext) -> None:
    """Show general statistics about the film club via reply keyboard button."""
    await state.clear()
    logger.info("User %s requested stats", message.from_user.id)
    async with AsyncSessionLocal() as db:
        try:
            group = await _resolve_group(db, message.chat.id, message.chat.type)
            if not group:
                await message.answer("ℹ️ Группа не найдена.")
                return

            stats = await _collect_stats(db, group.id)
            if stats is None:
                await message.answer("❌ Ошибка: статусы не инициализированы.")
                return

            response = _format_stats_message(stats)
            await message.answer(response)

        except Exception as e:
            logger.exception("Error showing stats: %s", e)
            await message.answer(
                "❌ Произошла ошибка при получении статистики."
            )


# ── Private helpers ──────────────────────────────────────────────────────


def _format_search_results(query: str, movies_data: List[dict]) -> str:
    """Format search results."""
    response = f"🔍 <b>Результаты поиска: \"{query}\"</b>\n\n"

    for data in movies_data:
        movie = data['movie']
        rating_count = data['rating_count']
        avg_rating = data['avg_rating']
        proposer_name = data['proposer_name']

        year_str = format_year_suffix(movie.year)

        response += f"<b>{movie.title}</b>{year_str}\n"

        if rating_count > 0:
            response += f"⭐ {avg_rating:.2f} ({rating_count} оценок)\n"
        else:
            response += "Нет оценок\n"

        response += f"Предложил: {proposer_name}\n"
        response += f"#{data['rank']} в общем рейтинге\n\n"

    response += f"Найдено: {len(movies_data)} фильм(ов)"
    return response


async def _collect_stats(
    db: AsyncSession,
    group_id: int,
) -> Optional[dict]:
    """Collect all statistics for the group. Returns None if statuses not initialized."""
    completed_status = await get_status_by_code(db, STATUS_COMPLETED)
    if not completed_status:
        return None

    total_sessions = (await db.execute(
        select(func.count(Session.id))
        .where(Session.group_id == group_id)
        .where(Session.status_id == completed_status.id)
    )).scalar()

    total_movies = (await db.execute(
        select(func.count(Movie.id))
        .join(Session, Movie.session_id == Session.id)
        .where(Session.group_id == group_id)
        .where(Session.status_id == completed_status.id)
        .where(
            or_(
                Movie.id == Session.winner_slot1_id,
                Movie.id == Session.winner_slot2_id,
            )
        )
    )).scalar()

    total_participants = (await db.execute(
        select(func.count(func.distinct(Movie.user_id)))
        .join(Session, Movie.session_id == Session.id)
        .where(Session.group_id == group_id)
    )).scalar()

    total_ratings = (await db.execute(
        select(func.count(Rating.id))
        .join(Movie, Rating.movie_id == Movie.id)
        .join(Session, Movie.session_id == Session.id)
        .where(Session.group_id == group_id)
    )).scalar()

    return {
        'sessions': total_sessions,
        'movies': total_movies,
        'participants': total_participants,
        'ratings': total_ratings,
    }


def _format_stats_message(stats: dict) -> str:
    """Format statistics into a user-facing message."""
    return (
        "📊 <b>СТАТИСТИКА КИНОКЛУБА</b>\n\n"
        f"🎬 Сессий завершено: <b>{stats['sessions']}</b>\n"
        f"🎥 Фильмов просмотрено: <b>{stats['movies']}</b>\n"
        f"👥 Участников: <b>{stats['participants']}</b>\n"
        f"⭐ Оценок выставлено: <b>{stats['ratings']}</b>\n"
    )
