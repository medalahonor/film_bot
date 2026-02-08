"""Admin commands (private chat only)."""
import logging
from datetime import datetime
from typing import Optional, List, Tuple

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from bot.database.models import Session, Group, Movie, Rating, User
from bot.database.session import AsyncSessionLocal
from bot.database.repositories import (
    get_or_create_group,
    get_user_by_username,
)
from bot.formatters import format_year_suffix
from bot.services.kinopoisk import (
    parse_movie_data,
    format_movie_info,
    KinopoiskParserError,
)
from bot.keyboards import get_confirmation_keyboard, get_cancel_keyboard
from bot.config import config
from bot.utils import try_delete_message, replace_bot_message, abort_flow, finish_flow

logger = logging.getLogger(__name__)

router = Router()


class AdminAddMovieState(StatesGroup):
    """States for adding movie manually."""
    waiting_for_url = State()
    waiting_for_date = State()
    waiting_for_proposer = State()


class AdminAddRatingsState(StatesGroup):
    """States for adding ratings manually."""
    waiting_for_ratings = State()


@router.message(Command("admin_help"))
async def show_admin_help(message: Message) -> None:
    """Show admin help."""
    if message.chat.type != 'private':
        return

    help_text = (
        "👑 <b>АДМИНСКИЕ КОМАНДЫ</b>\n\n"

        "<b>Управление фильмами:</b>\n"
        "/add_movie - Добавить фильм-победитель вручную\n"
        "/add_ratings &lt;movie_id&gt; - Добавить рейтинги для фильма\n"
        "/list_movies - Показать список всех фильмов\n"
        "/delete_movie &lt;movie_id&gt; - Удалить фильм\n\n"

        "<b>Управление сессиями:</b>\n"
        "/list_sessions - Показать все сессии\n"
        "/cancel_session - Отменить текущую сессию (можно и в группе)\n\n"

        "<b>Статистика:</b>\n"
        "/db_stats - Детальная статистика по БД\n"
        "/export_leaderboard - Экспортировать таблицу лидеров (CSV)\n\n"

        "💡 Все команды работают только в личных сообщениях, "
        "кроме /cancel_session."
    )

    await message.answer(help_text)


@router.message(Command("add_movie"))
async def start_add_movie(message: Message, state: FSMContext) -> None:
    """Start adding movie manually (private chat only)."""
    if message.chat.type != 'private':
        return

    await state.clear()
    await try_delete_message(message)

    await state.set_state(AdminAddMovieState.waiting_for_url)

    bot_msg = await message.answer(
        "📝 <b>Добавление фильма вручную</b>\n\n"
        "Отправьте ссылку на Кинопоиск или название фильма:",
        reply_markup=get_cancel_keyboard(),
    )
    await state.update_data(bot_message_id=bot_msg.message_id)


@router.message(AdminAddMovieState.waiting_for_url)
async def handle_movie_url(message: Message, state: FSMContext) -> None:
    """Handle movie URL or title."""
    url = message.text.strip()
    await try_delete_message(message)

    try:
        movie_data = await parse_movie_data(url)
        await state.update_data(movie_data=movie_data)

        info = await format_movie_info(movie_data)
        await replace_bot_message(
            message, state,
            f"{info}\n\n<b>Подтвердить?</b>",
            reply_markup=get_confirmation_keyboard("add_movie"),
        )
    except KinopoiskParserError as e:
        await replace_bot_message(
            message, state,
            f"❌ {str(e)}\n\n"
            "Отправьте ссылку на Кинопоиск или название фильма:",
        )


@router.callback_query(F.data == "confirm:add_movie:yes")
async def confirm_add_movie(callback: CallbackQuery, state: FSMContext) -> None:
    """Confirm adding movie."""
    data = await state.get_data()
    movie_data = data.get('movie_data')

    if not movie_data:
        await callback.answer("❌ Данные не найдены")
        return

    await state.update_data(movie_data=movie_data)
    await state.set_state(AdminAddMovieState.waiting_for_date)

    await replace_bot_message(
        callback.message, state,
        "📅 Укажите дату киноклуба (формат: ДД.ММ.ГГГГ):",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "confirm:add_movie:no")
async def cancel_add_movie(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel adding movie."""
    await abort_flow(
        callback.message, state,
        "❌ Добавление фильма отменено.",
    )
    await callback.answer()


@router.message(AdminAddMovieState.waiting_for_date)
async def handle_movie_date(message: Message, state: FSMContext) -> None:
    """Handle movie date."""
    date_str = message.text.strip()
    await try_delete_message(message)

    try:
        date = datetime.strptime(date_str, "%d.%m.%Y")
        await state.update_data(date=date)
        await state.set_state(AdminAddMovieState.waiting_for_proposer)

        await replace_bot_message(
            message, state,
            "👤 Кто предложил фильм? (username без @, или пропустите: /skip)",
            reply_markup=get_cancel_keyboard(),
        )
    except ValueError:
        await replace_bot_message(
            message, state,
            "⚠️ Неверный формат даты. Используйте: ДД.ММ.ГГГГ\n"
            "Например: 15.03.2023\n\n"
            "📅 Укажите дату киноклуба (формат: ДД.ММ.ГГГГ):",
        )


@router.message(Command("skip"))
async def skip_proposer(message: Message, state: FSMContext) -> None:
    """Skip proposer step."""
    current_state = await state.get_state()
    if current_state == AdminAddMovieState.waiting_for_proposer.state:
        await try_delete_message(message)
        await finalize_add_movie(message, state, proposer_username=None)


@router.message(AdminAddMovieState.waiting_for_proposer)
async def handle_movie_proposer(message: Message, state: FSMContext) -> None:
    """Handle movie proposer."""
    proposer_username = message.text.strip().lstrip('@')
    await try_delete_message(message)
    await finalize_add_movie(message, state, proposer_username)


async def finalize_add_movie(
    message: Message,
    state: FSMContext,
    proposer_username: Optional[str],
) -> None:
    """Finalize adding movie to database."""
    data = await state.get_data()
    movie_data = data.get('movie_data')
    date = data.get('date')

    if not movie_data or not date:
        await abort_flow(message, state, "❌ Ошибка: недостаточно данных")
        return

    async with AsyncSessionLocal() as db:
        try:
            group = await get_or_create_group(db, config.GROUP_ID, "Film Club")
            user = await _resolve_proposer(db, proposer_username)

            session = await _create_completed_session(
                db, group.id, message.from_user.id, date,
            )
            movie = await _create_movie(db, session.id, user.id, movie_data)

            session.winner_slot1_id = movie.id
            await db.commit()

            await finish_flow(message, state)

            await message.answer(
                f"✅ <b>Фильм добавлен!</b>\n\n"
                f"ID фильма: <code>{movie.id}</code>\n"
                f"Сессия: {session.id}\n\n"
                f"Теперь добавьте рейтинги командой:\n"
                f"/add_ratings {movie.id}"
            )
            logger.info("Admin %s added movie %s", message.from_user.id, movie.id)

        except Exception as e:
            logger.exception("Error adding movie: %s", e)
            await abort_flow(
                message, state,
                "❌ Произошла ошибка при добавлении фильма.",
            )


@router.message(Command("add_ratings"))
async def start_add_ratings(message: Message, state: FSMContext) -> None:
    """Start adding ratings manually (private chat only)."""
    if message.chat.type != 'private':
        return

    await state.clear()

    movie_id = _parse_movie_id_arg(message.text)
    await try_delete_message(message)

    if movie_id is None:
        await message.answer("⚠️ Укажите ID фильма: /add_ratings <movie_id>")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Movie).where(Movie.id == movie_id)
        )
        movie = result.scalar_one_or_none()

        if not movie:
            await message.answer(f"❌ Фильм с ID {movie_id} не найден.")
            return

        year_str = format_year_suffix(movie.year)
        bot_msg = await message.answer(
            f"📊 <b>Добавление рейтингов для фильма:</b>\n"
            f"🎬 {movie.title}{year_str}\n\n"
            f"Отправьте рейтинги в формате:\n"
            f"<code>@username1 8\n"
            f"@username2 9\n"
            f"user3 7</code>\n\n"
            f"Или просто числа (если не важны авторы):\n"
            f"<code>8 9 7 10 6</code>",
            reply_markup=get_cancel_keyboard(),
        )

        await state.update_data(movie_id=movie_id, bot_message_id=bot_msg.message_id)
        await state.set_state(AdminAddRatingsState.waiting_for_ratings)


@router.message(AdminAddRatingsState.waiting_for_ratings)
async def handle_add_ratings(message: Message, state: FSMContext) -> None:
    """Handle ratings input."""
    data = await state.get_data()
    movie_id = data.get('movie_id')
    text = message.text.strip()

    await try_delete_message(message)

    if not movie_id:
        await abort_flow(message, state, "❌ Ошибка: ID фильма не найден")
        return

    ratings = _parse_ratings_input(text)
    if not ratings:
        await replace_bot_message(
            message, state,
            "⚠️ Не удалось распознать рейтинги.\n\n"
            "Отправьте рейтинги в формате:\n"
            "<code>@username1 8\n@username2 9</code>\n\n"
            "Или просто числа: <code>8 9 7 10 6</code>",
        )
        return

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Movie).where(Movie.id == movie_id)
            )
            movie = result.scalar_one_or_none()

            if not movie:
                await abort_flow(message, state, "❌ Фильм не найден.")
                return

            added_count = await _save_ratings_batch(
                db, movie.session_id, movie_id, ratings,
            )
            await db.commit()

            avg_rating = await _get_movie_avg_rating(db, movie_id)

            await finish_flow(message, state)

            await message.answer(
                f"✅ <b>Добавлено {added_count} рейтингов</b>\n"
                f"Средняя оценка: ⭐ {avg_rating:.2f}"
            )
            logger.info(
                "Admin %s added %d ratings for movie %s",
                message.from_user.id, added_count, movie_id,
            )

        except Exception as e:
            logger.exception("Error adding ratings: %s", e)
            await abort_flow(
                message, state,
                "❌ Произошла ошибка при добавлении рейтингов.",
            )


@router.message(Command("list_movies"))
async def list_movies(message: Message) -> None:
    """List all movies in database (private chat only)."""
    if message.chat.type != 'private':
        return

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Movie, Session.status)
                .join(Session, Movie.session_id == Session.id)
                .order_by(Movie.created_at.desc())
                .limit(20)
            )
            rows = result.all()

            if not rows:
                await message.answer("ℹ️ Нет фильмов в базе данных.")
                return

            response = "<b>📋 Последние 20 фильмов:</b>\n\n"

            for movie, session_status in rows:
                year_str = format_year_suffix(movie.year)
                response += (
                    f"ID: <code>{movie.id}</code>\n"
                    f"🎬 {movie.title}{year_str}\n"
                    f"Сессия: {movie.session_id} ({session_status})\n"
                    f"Слот: {movie.slot}\n\n"
                )

            await message.answer(response)

        except Exception as e:
            logger.exception("Error listing movies: %s", e)
            await message.answer("❌ Произошла ошибка.")


@router.message(Command("db_stats"))
async def show_db_stats(message: Message) -> None:
    """Show detailed database statistics (private chat only)."""
    if message.chat.type != 'private':
        return

    async with AsyncSessionLocal() as db:
        try:
            users_count = (await db.execute(select(func.count(User.id)))).scalar()
            groups_count = (await db.execute(select(func.count(Group.id)))).scalar()
            sessions_count = (await db.execute(select(func.count(Session.id)))).scalar()
            movies_count = (await db.execute(select(func.count(Movie.id)))).scalar()
            ratings_count = (await db.execute(select(func.count(Rating.id)))).scalar()

            response = (
                "📊 <b>СТАТИСТИКА БАЗЫ ДАННЫХ</b>\n\n"
                f"👥 Пользователей: {users_count}\n"
                f"🏢 Групп: {groups_count}\n"
                f"📅 Сессий: {sessions_count}\n"
                f"🎬 Фильмов: {movies_count}\n"
                f"⭐ Рейтингов: {ratings_count}\n"
            )

            await message.answer(response)

        except Exception as e:
            logger.exception("Error showing DB stats: %s", e)
            await message.answer("❌ Произошла ошибка.")


# ── Private helpers ──────────────────────────────────────────────────────


def _parse_movie_id_arg(text: str) -> Optional[int]:
    """Parse movie ID from command text like '/add_ratings 42'."""
    try:
        parts = text.split()
        if len(parts) != 2:
            return None
        return int(parts[1])
    except (ValueError, IndexError):
        return None


def _parse_ratings_input(text: str) -> List[Tuple[Optional[str], int]]:
    """Parse ratings input text into list of (username_or_none, rating)."""
    ratings: List[Tuple[Optional[str], int]] = []

    for line in text.split('\n'):
        parts = line.strip().split()
        if len(parts) == 2:
            username, rating_str = parts
            try:
                rating = int(rating_str)
                if 1 <= rating <= 10:
                    ratings.append((username.lstrip('@'), rating))
            except ValueError:
                pass
        elif len(parts) == 1:
            try:
                rating = int(parts[0])
                if 1 <= rating <= 10:
                    ratings.append((None, rating))
            except ValueError:
                pass

    return ratings


async def _resolve_proposer(
    db,
    proposer_username: Optional[str],
) -> User:
    """Find existing user by username or create a placeholder."""
    user = None
    if proposer_username:
        user = await get_user_by_username(db, proposer_username)

    if not user:
        user = User(
            telegram_id=0,
            username=proposer_username or "Unknown",
            first_name=proposer_username or "Unknown",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def _create_completed_session(
    db,
    group_id: int,
    created_by_telegram_id: int,
    date: datetime,
) -> Session:
    """Create a completed session for manual movie addition."""
    session = Session(
        group_id=group_id,
        created_by=created_by_telegram_id,
        status='completed',
        created_at=date,
        completed_at=date,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _create_movie(
    db,
    session_id: int,
    user_id: int,
    movie_data: dict,
) -> Movie:
    """Create a movie record from parsed data."""
    movie = Movie(
        session_id=session_id,
        user_id=user_id,
        slot=1,
        kinopoisk_url=movie_data['kinopoisk_url'],
        kinopoisk_id=movie_data['kinopoisk_id'],
        title=movie_data['title'],
        year=movie_data['year'],
        genres=movie_data['genres'],
        description=movie_data['description'],
        poster_url=movie_data['poster_url'],
        kinopoisk_rating=movie_data['kinopoisk_rating'],
    )
    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    return movie


async def _save_ratings_batch(
    db,
    session_id: int,
    movie_id: int,
    ratings: List[Tuple[Optional[str], int]],
) -> int:
    """Save a batch of ratings, creating placeholder users as needed.

    Returns the number of ratings added.
    """
    added_count = 0

    for username, rating in ratings:
        user = None
        if username:
            user = await get_user_by_username(db, username)

        if not user:
            user = User(
                telegram_id=0,
                username=username or f"User{added_count}",
                first_name=username or f"User{added_count}",
            )
            db.add(user)
            await db.flush()

        db.add(Rating(
            session_id=session_id,
            movie_id=movie_id,
            user_id=user.id,
            rating=rating,
        ))
        added_count += 1

    return added_count


async def _get_movie_avg_rating(db, movie_id: int) -> float:
    """Get the average rating for a movie."""
    result = await db.execute(
        select(func.avg(Rating.rating))
        .where(Rating.movie_id == movie_id)
    )
    avg_rating = result.scalar()
    return round(float(avg_rating), 2) if avg_rating else 0.0
