"""Film proposals handling."""
import html as html_lib
import logging
import re
from typing import List, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Session, User, Movie
from bot.database.session import AsyncSessionLocal
from bot.database.status_manager import STATUS_COLLECTING
from bot.database.repositories import (
    get_group_by_telegram_id,
    get_active_session,
    get_or_create_user,
)
from bot.formatters import format_user_display_name
from bot.services.kinopoisk import (
    parse_movie_data,
    format_movie_info,
    is_valid_kinopoisk_url,
    KinopoiskParserError,
)
from bot.keyboards import (
    BTN_PROPOSE, BTN_NEW_SESSION,
    get_slot_selection_keyboard, get_cancel_keyboard, get_main_menu_keyboard,
)
from bot.utils import try_delete_message, replace_bot_message, abort_flow

logger = logging.getLogger(__name__)

router = Router()


class ProposeButtonState(StatesGroup):
    """States for 'Предложить фильм' button flow."""
    waiting_for_url = State()


def extract_kinopoisk_urls(text: str) -> List[str]:
    """Extract Kinopoisk URLs from message text.

    Returns:
        List of valid, deduplicated Kinopoisk URLs
    """
    url_pattern = r'https?://(?:www\.)?kinopoisk\.ru/film/\d+/?(?:\S*)?'
    urls = re.findall(url_pattern, text)

    valid_urls = []
    seen_ids: set = set()

    for url in urls:
        if is_valid_kinopoisk_url(url):
            from bot.services.kinopoisk import extract_kinopoisk_id
            film_id = extract_kinopoisk_id(url)
            if film_id and film_id not in seen_ids:
                seen_ids.add(film_id)
                valid_urls.append(f"https://www.kinopoisk.ru/film/{film_id}/")

    return valid_urls


async def update_pinned_message(
    db: AsyncSession,
    session: Session,
    message: Message,
) -> None:
    """Update pinned message with list of participants who proposed films."""
    result = await db.execute(
        select(Movie.user_id)
        .where(Movie.session_id == session.id)
        .distinct()
    )
    user_ids = [row[0] for row in result.all()]

    result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users = result.scalars().all()

    usernames = [
        format_user_display_name(u.username, u.first_name, fallback="Пользователь")
        for u in users
    ]

    updated_text = (
        "🎬 <b>СБОР ПРЕДЛОЖЕНИЙ ОТКРЫТ!</b>\n\n"
        "Чтобы предложить фильм, нажмите кнопку\n"
        "📝 <b>Предложить фильм</b> в меню бота.\n\n"
        "─────────────────\n"
        f"✅ <b>Уже предложили ({len(usernames)}):</b>\n"
    )

    updated_text += ", ".join(usernames) if usernames else "(пусто)"

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=session.pinned_message_id,
            text=updated_text,
        )
    except Exception as e:
        logger.warning("Failed to update pinned message: %s", e)


# ── «Предложить фильм» button flow ──────────────────────────────────────


@router.message(F.text == BTN_PROPOSE)
async def propose_film_button(message: Message, state: FSMContext) -> None:
    """Handle 'Предложить фильм' button — start propose flow."""
    logger.info("User %s started propose flow", message.from_user.id)
    await state.clear()
    await try_delete_message(message)

    async with AsyncSessionLocal() as db:
        try:
            session = await _get_collecting_session(db, message)
            if not session:
                return

            await state.set_state(ProposeButtonState.waiting_for_url)

            bot_msg = await message.answer(
                "🎬 Отправьте ссылку на фильм в Кинопоиске:",
                reply_markup=get_cancel_keyboard(),
            )
            await state.update_data(bot_message_id=bot_msg.message_id)
        except Exception as e:
            logger.exception("Error in propose flow for user %s: %s", message.from_user.id, e)
            await message.answer(
                "❌ Произошла ошибка.",
                reply_markup=get_main_menu_keyboard(),
            )


@router.message(ProposeButtonState.waiting_for_url)
async def propose_url_received(message: Message, state: FSMContext) -> None:
    """Handle URL input in propose flow.

    Parses the film, shows its card, and presents inline slot buttons.
    """
    user_text = message.text or ""
    from_user = message.from_user
    logger.info("User %s sent proposal URL: %s", from_user.id, user_text[:100])

    await try_delete_message(message)

    urls = extract_kinopoisk_urls(user_text)
    if not urls:
        logger.info("User %s sent invalid URL: %s", from_user.id, user_text[:100])
        text = (
            "⚠️ Не найдена корректная ссылка на Кинопоиск.\n\n"
            "Пример: https://www.kinopoisk.ru/film/301/\n\n"
            "🎬 Отправьте ссылку на фильм в Кинопоиске:"
        )
        await replace_bot_message(message, state, text)
        return

    url = urls[0]
    async with AsyncSessionLocal() as db:
        try:
            session = await _get_collecting_session(db, message)
            if not session:
                return

            user = await get_or_create_user(
                db, from_user.id, from_user.username,
                from_user.first_name, from_user.last_name,
            )

            movie_data = await _parse_movie_safe(url, message, state)
            if not movie_data:
                return

            duplicate_msg = await _check_duplicate(db, session, movie_data)
            if duplicate_msg:
                await replace_bot_message(message, state, duplicate_msg)
                return

            await _show_slot_selection(
                message, state, from_user, movie_data, session.id, user.id,
            )

        except Exception as e:
            logger.exception("Error in propose flow: %s", e)
            await abort_flow(
                message, state,
                "❌ Произошла ошибка.",
                reply_markup=get_main_menu_keyboard(),
            )


@router.callback_query(F.data.startswith("slot:"))
async def handle_slot_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle slot selection for single movie proposal.

    callback_data format: ``slot:<slot>:<telegram_user_id>``
    """
    try:
        parts = callback.data.split(":")
        slot = int(parts[1])
        allowed_user_id = int(parts[2]) if len(parts) > 2 else None

        if allowed_user_id is not None and callback.from_user.id != allowed_user_id:
            logger.info(
                "User %s tried to select slot for another user %s",
                callback.from_user.id, allowed_user_id,
            )
            await callback.answer(
                "⛔ Эта кнопка не для вас — слот может выбрать только тот, кто предложил фильм.",
                show_alert=True,
            )
            return

        data = await state.get_data()
        movie_data = data.get('movie_data')
        session_id = data.get('session_id')
        user_id = data.get('user_id')

        if not all([movie_data, session_id, user_id]):
            await callback.answer("❌ Данные не найдены. Попробуйте ещё раз.")
            return

        async with AsyncSessionLocal() as db:
            await _replace_old_movie_in_slot(db, session_id, user_id, slot)

            movie = Movie(
                session_id=session_id,
                user_id=user_id,
                slot=slot,
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

            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one()

            await update_pinned_message(db, session, callback.message)

        await state.clear()

        logger.info(
            "User %s added movie '%s' to slot %s in session %s",
            callback.from_user.id, movie_data.get('title'), slot, session_id,
        )

        await callback.message.edit_text(
            callback.message.html_text
            + f"\n\n✅ <b>Фильм добавлен в слот {slot}</b>"
        )
        await callback.answer(f"✅ Фильм добавлен в слот {slot}")

        await callback.message.answer(
            "📝 Предложение принято!",
            reply_markup=get_main_menu_keyboard(),
        )

    except Exception as e:
        logger.exception("Error handling slot selection: %s", e)
        await callback.answer("❌ Произошла ошибка")


# ── Private helpers ──────────────────────────────────────────────────────


async def _get_collecting_session(
    db: AsyncSession,
    message: Message,
) -> Optional[Session]:
    """Get the active collecting session, or send an error and return None."""
    group = await get_group_by_telegram_id(db, message.chat.id)
    if not group:
        await message.answer(
            "ℹ️ Группа не найдена.",
            reply_markup=get_main_menu_keyboard(),
        )
        return None

    session = await get_active_session(db, group.id, STATUS_COLLECTING)
    if not session:
        await message.answer(
            "⚠️ Нет активной сессии в статусе «сбор предложений».\n"
            f"Нажмите «{BTN_NEW_SESSION}» для создания новой.",
            reply_markup=get_main_menu_keyboard(),
        )
        return None

    return session


async def _parse_movie_safe(url: str, message: Message, state: FSMContext):
    """Parse movie data from URL, handling errors gracefully.

    Returns movie_data dict on success, or None on failure (error shown to user).
    """
    try:
        return await parse_movie_data(url)
    except KinopoiskParserError as e:
        text = (
            f"❌ {html_lib.escape(str(e))}\n\n"
            "🎬 Отправьте ссылку на фильм в Кинопоиске:"
        )
        await replace_bot_message(message, state, text)
        return None
    except Exception as e:
        logger.exception("Error parsing movie from %s: %s", url, e)
        text = (
            "❌ Произошла ошибка при обработке ссылки. "
            "Попробуйте позже.\n\n"
            "🎬 Отправьте ссылку на фильм в Кинопоиске:"
        )
        await replace_bot_message(message, state, text)
        return None


async def _check_duplicate(
    db: AsyncSession,
    session: Session,
    movie_data: dict,
) -> Optional[str]:
    """Check if movie already proposed in this session.

    Returns error message string if duplicate, otherwise None.
    """
    result = await db.execute(
        select(Movie)
        .where(Movie.session_id == session.id)
        .where(Movie.kinopoisk_id == movie_data["kinopoisk_id"])
    )
    existing_movie = result.scalar_one_or_none()

    if not existing_movie:
        return None

    result = await db.execute(
        select(User).where(User.id == existing_movie.user_id)
    )
    proposer = result.scalar_one()
    proposer_name = (
        f"@{proposer.username}"
        if proposer.username
        else html_lib.escape(proposer.first_name or "Пользователь")
    )
    return (
        f"⚠️ Фильм <b>{html_lib.escape(movie_data['title'])}</b> "
        f"уже предложен участником {proposer_name}\n\n"
        "🎬 Отправьте другую ссылку:"
    )


async def _show_slot_selection(
    message: Message,
    state: FSMContext,
    from_user,
    movie_data: dict,
    session_id: int,
    user_id: int,
) -> None:
    """Store movie data in FSM and show film card with slot selection buttons."""
    await state.update_data(
        movie_data=movie_data,
        session_id=session_id,
        user_id=user_id,
    )
    await state.set_state(None)

    proposer_display = (
        f"@{from_user.username}"
        if from_user.username
        else html_lib.escape(from_user.first_name or "Пользователь")
    )

    response = await format_movie_info(movie_data)
    response += f"\n\n👤 Предложил: {proposer_display}"
    response += "\n\n<b>Выберите слот:</b>"

    slot_keyboard = get_slot_selection_keyboard(from_user.id)
    await replace_bot_message(message, state, response, slot_keyboard)


async def _replace_old_movie_in_slot(
    db: AsyncSession,
    session_id: int,
    user_id: int,
    slot: int,
) -> None:
    """Delete old movie by this user in this slot if exists."""
    result = await db.execute(
        select(Movie)
        .where(Movie.session_id == session_id)
        .where(Movie.user_id == user_id)
        .where(Movie.slot == slot)
    )
    old_movie = result.scalar_one_or_none()
    if old_movie:
        await db.delete(old_movie)
