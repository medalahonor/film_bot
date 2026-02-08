"""Rating handlers.

The rating flow works as follows:
1. Someone presses "⭐ Оценить фильмы" — the bot sends ONE message per
   winner movie (with an inline 1-10 keyboard) visible to the whole group,
   plus a scoreboard message below.
2. Inline keyboards stay for everyone. When a user taps a rating button,
   the bot saves/updates the rating, shows a popup confirmation, and edits
   the shared scoreboard message with the latest data.
3. The scoreboard shows who gave what rating to each movie.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Session, Movie, Rating, User
from bot.database.session import AsyncSessionLocal
from bot.database.status_manager import get_status_by_code, STATUS_RATING, STATUS_COMPLETED
from bot.database.repositories import (
    resolve_telegram_group_id,
    get_group_by_telegram_id,
    get_active_session,
    get_or_create_user,
    recalc_club_rating,
)
from bot.formatters import format_year_suffix, format_user_display_name
from bot.keyboards import get_rating_keyboard, BTN_RATE, BTN_COMPLETE_SESSION

logger = logging.getLogger(__name__)

router = Router()


# ── Helpers ───────────────────────────────────────────────────────────────


async def _get_active_rating_session(
    db: AsyncSession,
    chat_id: int,
    chat_type: str,
) -> Optional[Session]:
    """Return the active session in 'rating' status for the given chat."""
    group_telegram_id = resolve_telegram_group_id(chat_id, chat_type)
    group = await get_group_by_telegram_id(db, group_telegram_id)
    if not group:
        return None
    return await get_active_session(db, group.id, STATUS_RATING)


async def _get_winner_movies(
    db: AsyncSession,
    session: Session,
) -> List[Movie]:
    """Return winner movies for the session, sorted by slot."""
    winner_ids = [
        wid
        for wid in [session.winner_slot1_id, session.winner_slot2_id]
        if wid is not None
    ]
    if not winner_ids:
        return []

    result = await db.execute(
        select(Movie).where(Movie.id.in_(winner_ids))
    )
    return sorted(result.scalars().all(), key=lambda m: m.slot)


async def _build_scoreboard_text(
    db: AsyncSession,
    session: Session,
    movies: List[Movie],
) -> str:
    """Build the scoreboard text showing all ratings per movie."""
    movie_ids = [m.id for m in movies]

    result = await db.execute(
        select(Rating)
        .where(Rating.session_id == session.id)
        .where(Rating.movie_id.in_(movie_ids))
        .options(selectinload(Rating.user))
    )
    all_ratings = result.scalars().all()

    ratings_by_movie: Dict[int, List[Rating]] = {m.id: [] for m in movies}
    for rating in all_ratings:
        ratings_by_movie.setdefault(rating.movie_id, []).append(rating)

    text = "📊 <b>ТАБЛИЦА ОЦЕНОК</b>\n"

    for movie in movies:
        year_str = format_year_suffix(movie.year)
        text += f"\n📍 <b>Слот {movie.slot}:</b> {movie.title}{year_str}\n"

        movie_ratings = ratings_by_movie.get(movie.id, [])
        if not movie_ratings:
            text += "  <i>Ещё никто не оценил</i>\n"
            continue

        for rating in sorted(movie_ratings, key=lambda r: r.created_at):
            display_name = format_user_display_name(
                rating.user.username, rating.user.first_name,
            )
            text += f"  👤 {display_name} — ⭐ <b>{rating.rating}</b>/10\n"

        avg_rating = sum(r.rating for r in movie_ratings) / len(movie_ratings)
        text += f"  Средняя: <b>{avg_rating:.2f}</b>/10\n"

    return text


async def _update_scoreboard(
    bot,
    chat_id: int,
    scoreboard_msg_id: int,
    db: AsyncSession,
    session: Session,
    movies: List[Movie],
) -> None:
    """Edit the scoreboard message with fresh data."""
    text = await _build_scoreboard_text(db, session, movies)
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=scoreboard_msg_id,
        )
    except Exception as exc:
        if "message is not modified" not in str(exc):
            logger.warning("Failed to update scoreboard: %s", exc)


async def _save_or_update_rating(
    db: AsyncSession,
    session: Session,
    movie_id: int,
    user: User,
    rating_value: int,
) -> str:
    """Save or update a user's rating. Returns action description."""
    result = await db.execute(
        select(Rating)
        .where(Rating.session_id == session.id)
        .where(Rating.movie_id == movie_id)
        .where(Rating.user_id == user.id)
    )
    existing_rating = result.scalar_one_or_none()

    if existing_rating:
        existing_rating.rating = rating_value
        action = "обновлена"
    else:
        db.add(Rating(
            session_id=session.id,
            movie_id=movie_id,
            user_id=user.id,
            rating=rating_value,
        ))
        action = "сохранена"

    await db.commit()

    # Update the stored club_rating average
    await recalc_club_rating(db, movie_id)

    return action


# ── Handlers ──────────────────────────────────────────────────────────────


@router.message(F.text == BTN_RATE)
async def rate_movies(message: Message, state: FSMContext) -> None:
    """Send rating interface to the group: inline 1-10 keyboards + scoreboard."""
    await state.clear()
    logger.info("User %s requested rating interface", message.from_user.id)
    async with AsyncSessionLocal() as db:
        try:
            session = await _get_active_rating_session(
                db, message.chat.id, message.chat.type,
            )
            if not session:
                await message.answer(
                    "ℹ️ Нет активной сессии в статусе 'выставление рейтингов'.\n\n"
                    "Рейтинги можно выставлять только после завершения голосования."
                )
                return

            movies = await _get_winner_movies(db, session)
            if not movies:
                await message.answer(
                    "⚠️ Не определены фильмы-победители. Завершите голосование."
                )
                return

            if session.rating_scoreboard_msg_id is not None:
                await message.answer(
                    "ℹ️ Сообщения для оценки уже отправлены.\n"
                    "Используйте кнопки с оценками выше ☝️"
                )
                return

            await _send_rating_interface(message, db, session, movies)

        except Exception as exc:
            logger.exception("Error showing rating interface: %s", exc)
            await message.answer(
                "❌ Произошла ошибка при показе интерфейса оценки."
            )


@router.callback_query(F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery) -> None:
    """Handle inline rating button press.

    Callback data format: rate:<movie_id>:<rating>
    """
    try:
        parts = callback.data.split(":")
        movie_id = int(parts[1])
        rating_value = int(parts[2])

        if not (1 <= rating_value <= 10):
            await callback.answer("❌ Неверное значение рейтинга")
            return

        async with AsyncSessionLocal() as db:
            session = await _get_active_rating_session(
                db, callback.message.chat.id, callback.message.chat.type,
            )
            if not session:
                await callback.answer("❌ Нет активной сессии для оценки")
                return

            movie = await _validate_winner_movie(db, session, movie_id)
            if not movie:
                await callback.answer("❌ Фильм не найден в текущей сессии")
                return

            user = await get_or_create_user(
                db, callback.from_user.id, callback.from_user.username,
                callback.from_user.first_name, callback.from_user.last_name,
            )

            action = await _save_or_update_rating(
                db, session, movie_id, user, rating_value,
            )

            year_str = format_year_suffix(movie.year)
            await callback.answer(
                f"✅ Оценка {action}: {rating_value}/10\n"
                f"{movie.title}{year_str}"
            )

            logger.info(
                "User %s rated movie %s with %s (%s)",
                user.id, movie_id, rating_value, action,
            )

            await _refresh_scoreboard(callback, db, session)

    except Exception as exc:
        logger.exception("Error handling rating: %s", exc)
        await callback.answer("❌ Произошла ошибка")


@router.message(F.text == BTN_COMPLETE_SESSION)
async def complete_session(message: Message, state: FSMContext) -> None:
    """Complete current session via reply keyboard button."""
    await state.clear()
    logger.info("User %s requested session completion", message.from_user.id)
    async with AsyncSessionLocal() as db:
        try:
            session = await _get_active_rating_session(
                db, message.chat.id, message.chat.type,
            )
            if not session:
                await message.answer(
                    "ℹ️ Нет активной сессии в статусе 'выставление рейтингов'."
                )
                return

            movies = await _get_winner_movies(db, session)
            if not movies:
                await message.answer("⚠️ Не определены фильмы-победители.")
                return

            response = await _format_final_stats(db, session, movies)

            # Update scoreboard one last time
            if session.rating_scoreboard_msg_id:
                await _update_scoreboard(
                    message.bot, message.chat.id,
                    session.rating_scoreboard_msg_id, db, session, movies,
                )

            # Mark session as completed
            completed_status = await get_status_by_code(db, STATUS_COMPLETED)
            if not completed_status:
                await message.answer("❌ Ошибка: статусы не инициализированы.")
                return

            session.status_id = completed_status.id
            session.completed_at = datetime.utcnow()
            await db.commit()

            response += (
                "✅ Сессия завершена!\n\n"
                "Смотрите таблицу лидеров: 🏆 Лидерборд"
            )
            await message.answer(response)

            logger.info("Session %s completed", session.id)

        except Exception as exc:
            logger.exception("Error completing session: %s", exc)
            await message.answer(
                "❌ Произошла ошибка при завершении сессии."
            )


# ── Private helpers ──────────────────────────────────────────────────────


async def _send_rating_interface(
    message: Message,
    db: AsyncSession,
    session: Session,
    movies: List[Movie],
) -> None:
    """Send rating messages with inline keyboards and scoreboard."""
    for movie in movies:
        year_str = format_year_suffix(movie.year)
        text = (
            f"🎬 <b>Оцените фильм:</b>\n"
            f"📍 Слот {movie.slot}: <b>{movie.title}</b>{year_str}\n\n"
            f"Выберите оценку от 1 до 10:"
        )
        sent_msg = await message.answer(
            text, reply_markup=get_rating_keyboard(movie.id),
        )
        if movie.slot == 1:
            session.rating_msg_slot1_id = sent_msg.message_id
        else:
            session.rating_msg_slot2_id = sent_msg.message_id

    scoreboard_text = await _build_scoreboard_text(db, session, movies)
    scoreboard_msg = await message.answer(scoreboard_text)
    session.rating_scoreboard_msg_id = scoreboard_msg.message_id

    await db.commit()

    logger.info(
        "Rating interface sent for session %s (movies: %s)",
        session.id, [m.id for m in movies],
    )


async def _validate_winner_movie(
    db: AsyncSession,
    session: Session,
    movie_id: int,
) -> Optional[Movie]:
    """Validate that a movie belongs to the session's winners and return it."""
    winner_ids = [
        wid
        for wid in [session.winner_slot1_id, session.winner_slot2_id]
        if wid is not None
    ]
    if movie_id not in winner_ids:
        return None

    result = await db.execute(
        select(Movie).where(Movie.id == movie_id)
    )
    return result.scalar_one_or_none()


async def _refresh_scoreboard(
    callback: CallbackQuery,
    db: AsyncSession,
    session: Session,
) -> None:
    """Refresh the scoreboard after a rating change."""
    if not session.rating_scoreboard_msg_id:
        return
    movies = await _get_winner_movies(db, session)
    await _update_scoreboard(
        callback.bot,
        callback.message.chat.id,
        session.rating_scoreboard_msg_id,
        db, session, movies,
    )


async def _format_final_stats(
    db: AsyncSession,
    session: Session,
    movies: List[Movie],
) -> str:
    """Format final rating statistics for session completion."""
    winner_ids = [m.id for m in movies]

    result = await db.execute(
        select(
            Rating.movie_id,
            func.count(Rating.id).label("count"),
            func.avg(Rating.rating).label("avg_rating"),
        )
        .where(Rating.session_id == session.id)
        .where(Rating.movie_id.in_(winner_ids))
        .group_by(Rating.movie_id)
    )
    rating_stats = {
        row.movie_id: (row.count, row.avg_rating) for row in result.all()
    }

    response = "📊 <b>ИТОГОВАЯ СТАТИСТИКА ОЦЕНОК</b>\n\n"

    for movie in movies:
        year_str = format_year_suffix(movie.year)
        count, avg_rating = rating_stats.get(movie.id, (0, 0))

        if count > 0:
            avg_rounded = round(float(avg_rating), 2)
            response += (
                f"🎬 <b>{movie.title}</b>{year_str}\n"
                f"   Средняя оценка: ⭐ <b>{avg_rounded:.2f}</b> "
                f"({count} оценок)\n\n"
            )
        else:
            response += (
                f"🎬 <b>{movie.title}</b>{year_str}\n"
                f"   Нет оценок\n\n"
            )

    return response
