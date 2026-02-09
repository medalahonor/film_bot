"""Admin panel handlers (private chat only).

Entry point: /admin command opens a reply-keyboard admin panel.
Navigation: reply-keyboard sub-menus with a ↩️ Назад button.
"""
import logging
import re
from typing import List, Optional, Tuple

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func, select

from bot.config import config
from bot.database.models import Session, Group, Movie, Rating, User
from bot.database.session import AsyncSessionLocal
from bot.database.repositories import (
    get_or_create_group,
    get_active_session_any,
    get_movies_paginated,
    search_movies_by_title,
    get_movie_by_id,
    delete_movie_by_id,
    recalc_club_rating,
    set_session_status,
    get_session_movies,
    create_completed_session_for_import,
    _get_or_create_system_user,
)
from bot.database.status_manager import (
    STATUS_COLLECTING,
    STATUS_VOTING,
    STATUS_RATING,
    STATUS_COMPLETED,
)
from bot.formatters import format_year_suffix
from bot.services.kinopoisk import (
    parse_movie_data,
    format_movie_info,
    KinopoiskParserError,
)
from bot.keyboards import (
    BTN_BACK,
    BTN_ADMIN_SESSIONS,
    BTN_ADMIN_MOVIES,
    BTN_ADMIN_BATCH,
    BTN_ADMIN_STATS,
    BTN_ADMIN_LOGS,
    BTN_ADMIN_EXIT,
    BTN_ADM_FORCE_VOTING,
    BTN_ADM_ADD_MOVIE,
    BTN_ADM_DEL_SLOT_MOVIE,
    BTN_ADM_CANCEL_SESSION,
    BTN_ADM_FORCE_FINISH_VOTE,
    BTN_ADM_SET_WINNER,
    BTN_ADM_BACK_COLLECTING,
    BTN_ADM_FORCE_COMPLETE,
    BTN_ADM_ADD_RATINGS,
    BTN_ADM_BACK_VOTING,
    BTN_ADM_MOVIE_LIST,
    BTN_ADM_MOVIE_SEARCH,
    BTN_ADM_CHANGE_GROUP,
    get_admin_menu_keyboard,
    get_admin_sessions_collecting_keyboard,
    get_admin_sessions_voting_keyboard,
    get_admin_sessions_rating_keyboard,
    get_admin_no_session_keyboard,
    get_admin_movies_keyboard,
    get_admin_back_keyboard,
    get_admin_movie_actions_keyboard,
    get_admin_movie_list_pagination,
    get_admin_delete_confirm_keyboard,
    get_confirmation_keyboard,
    get_main_menu_keyboard,
    get_admin_group_selector_keyboard,
)
from bot.utils import try_delete_message, replace_bot_message, abort_flow, finish_flow
from bot.log_handler import get_recent_logs

logger = logging.getLogger(__name__)

router = Router()

MOVIES_PER_PAGE = 5


# ── FSM States ───────────────────────────────────────────────────────────


class AdminMenuState(StatesGroup):
    """Top-level admin panel navigation."""
    select_group = State()
    main_menu = State()
    sessions_menu = State()
    movies_menu = State()


class AdminAddSlotMovieState(StatesGroup):
    """Add a movie to a slot in the active session."""
    waiting_for_url = State()
    waiting_for_slot = State()


class AdminAddRatingsState(StatesGroup):
    """Add ratings for a movie in the active session."""
    waiting_for_movie_choice = State()
    waiting_for_ratings = State()


class AdminSetWinnerState(StatesGroup):
    """Manually set a winner for a slot."""
    waiting_for_slot = State()
    waiting_for_movie_choice = State()


class AdminEditRatingState(StatesGroup):
    """Edit club rating for a movie."""
    waiting_for_rating = State()


class AdminSearchMovieState(StatesGroup):
    """Search movies by title."""
    waiting_for_query = State()


class AdminBatchImportState(StatesGroup):
    """Batch import movies with club ratings."""
    waiting_for_data = State()
    confirm = State()


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    """Open admin panel (private chat only)."""
    if message.chat.type != "private":
        return

    await state.clear()
    await try_delete_message(message)

    if len(config.GROUP_IDS) == 1:
        await state.update_data(admin_group_id=config.GROUP_IDS[0])
        await state.set_state(AdminMenuState.main_menu)
        bot_msg = await message.answer(
            "👑 <b>Админ-панель</b>\n\n"
            "Выберите раздел:",
            reply_markup=get_admin_menu_keyboard(),
        )
        await state.update_data(bot_message_id=bot_msg.message_id)
    else:
        await _show_group_selector(message, state)


async def _get_admin_group_id(state: FSMContext) -> Optional[int]:
    """Extract admin_group_id from FSM data."""
    data = await state.get_data()
    return data.get("admin_group_id")


async def _show_group_selector(message: Message, state: FSMContext) -> None:
    """Show inline keyboard for group selection."""
    await state.set_state(AdminMenuState.select_group)
    groups: List[Tuple[int, str]] = []
    async with AsyncSessionLocal() as db:
        for gid in config.GROUP_IDS:
            group = await get_or_create_group(db, gid)
            name = group.name or str(gid)
            groups.append((gid, name))

    bot_msg = await message.answer(
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите группу:",
        reply_markup=get_admin_group_selector_keyboard(groups),
    )
    await state.update_data(bot_message_id=bot_msg.message_id)


@router.callback_query(F.data.startswith("adm_group:"))
async def admin_select_group(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle group selection from inline keyboard."""
    group_tid = int(callback.data.split(":")[1])
    await callback.answer()
    await state.update_data(admin_group_id=group_tid)
    await state.set_state(AdminMenuState.main_menu)

    try:
        await callback.message.edit_text(
            "👑 <b>Админ-панель</b>\n\n"
            "Выберите раздел:",
        )
    except Exception:
        pass

    bot_msg = await callback.message.answer(
        "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=get_admin_menu_keyboard(),
    )
    await state.update_data(bot_message_id=bot_msg.message_id)


@router.message(F.text == BTN_ADM_CHANGE_GROUP)
async def admin_change_group(message: Message, state: FSMContext) -> None:
    """Switch to a different group."""
    await try_delete_message(message)
    await _show_group_selector(message, state)


# ══════════════════════════════════════════════════════════════════════════
# MAIN MENU NAVIGATION
# ══════════════════════════════════════════════════════════════════════════


@router.message(F.text == BTN_ADMIN_EXIT)
async def admin_exit(message: Message, state: FSMContext) -> None:
    """Exit admin panel and return to main menu."""
    await finish_flow(message, state)
    await try_delete_message(message)
    await message.answer(
        "↩️ Вы вышли из админ-панели.",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(F.text == BTN_BACK)
async def admin_back(message: Message, state: FSMContext) -> None:
    """Go back to admin main menu from any sub-menu."""
    await try_delete_message(message)
    await state.set_state(AdminMenuState.main_menu)
    await replace_bot_message(
        message, state,
        "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=get_admin_menu_keyboard(),
    )


# ══════════════════════════════════════════════════════════════════════════
# SESSIONS SUB-MENU
# ══════════════════════════════════════════════════════════════════════════


@router.message(F.text == BTN_ADMIN_SESSIONS)
async def admin_sessions(message: Message, state: FSMContext) -> None:
    """Show sessions sub-menu with context-sensitive actions."""
    await try_delete_message(message)
    await state.set_state(AdminMenuState.sessions_menu)

    async with AsyncSessionLocal() as db:
        group_tid = await _get_admin_group_id(state)
        group = await get_or_create_group(db, group_tid)
        session = await get_active_session_any(db, group.id)

        if not session:
            await replace_bot_message(
                message, state,
                "📋 <b>Сессии</b>\n\nНет активной сессии.",
                reply_markup=get_admin_no_session_keyboard(),
            )
            return

        text = await _format_session_info(db, session)
        keyboard = _get_session_keyboard(session.status)

        await replace_bot_message(
            message, state,
            text,
            reply_markup=keyboard,
        )


# ── Session actions: collecting ──────────────────────────────────────────


@router.message(F.text == BTN_ADM_FORCE_VOTING)
async def admin_force_voting(message: Message, state: FSMContext) -> None:
    """Force transition from collecting to voting."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_COLLECTING:
            await replace_bot_message(
                message, state,
                "⚠️ Нет сессии в статусе «сбор предложений».",
            )
            return

        ok = await set_session_status(db, session, STATUS_VOTING)
        if not ok:
            await replace_bot_message(message, state, "❌ Ошибка смены статуса.")
            return

        await replace_bot_message(
            message, state,
            "✅ Сессия переведена в статус <b>голосование</b>.\n\n"
            "⚠️ Опросы в группе не создавались. "
            "Используйте «Назначить победителя» или запустите голосование из группы.",
            reply_markup=get_admin_sessions_voting_keyboard(),
        )


@router.message(F.text == BTN_ADM_ADD_MOVIE)
async def admin_add_movie_start(message: Message, state: FSMContext) -> None:
    """Start adding a movie to the active session."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_COLLECTING:
            await replace_bot_message(
                message, state,
                "⚠️ Нет сессии в статусе «сбор предложений».",
            )
            return

    await state.set_state(AdminAddSlotMovieState.waiting_for_url)
    await state.update_data(return_to="sessions")
    await replace_bot_message(
        message, state,
        "🎬 <b>Добавить фильм в слот</b>\n\n"
        "Отправьте ссылку на Кинопоиск:",
        reply_markup=get_admin_back_keyboard(),
    )


@router.message(AdminAddSlotMovieState.waiting_for_url)
async def admin_add_movie_url(message: Message, state: FSMContext) -> None:
    """Handle movie URL for slot addition."""
    if message.text == BTN_BACK:
        await _return_to_sessions(message, state)
        return

    url = message.text.strip()
    await try_delete_message(message)

    try:
        movie_data = await parse_movie_data(url)
        await state.update_data(movie_data=movie_data)
        await state.set_state(AdminAddSlotMovieState.waiting_for_slot)

        info = await format_movie_info(movie_data)
        await replace_bot_message(
            message, state,
            f"{info}\n\nВыберите слот (1 или 2):",
            reply_markup=get_admin_back_keyboard(),
        )
    except KinopoiskParserError as e:
        await replace_bot_message(
            message, state,
            f"❌ {e}\n\nОтправьте ссылку на Кинопоиск:",
        )


@router.message(AdminAddSlotMovieState.waiting_for_slot)
async def admin_add_movie_slot(message: Message, state: FSMContext) -> None:
    """Handle slot selection for movie addition."""
    if message.text == BTN_BACK:
        await _return_to_sessions(message, state)
        return

    text = message.text.strip()
    await try_delete_message(message)

    if text not in ("1", "2"):
        await replace_bot_message(
            message, state,
            "⚠️ Введите <b>1</b> или <b>2</b>:",
        )
        return

    slot = int(text)
    data = await state.get_data()
    movie_data = data.get("movie_data")

    if not movie_data:
        await abort_flow(message, state, "❌ Данные фильма потеряны.")
        return

    async with AsyncSessionLocal() as db:
        try:
            session = await _get_active_session(db, await _get_admin_group_id(state))
            if not session:
                await abort_flow(message, state, "❌ Активная сессия не найдена.")
                return

            system_user = await _get_or_create_system_user(db)
            movie = Movie(
                session_id=session.id,
                user_id=system_user.id,
                slot=slot,
                kinopoisk_url=movie_data["kinopoisk_url"],
                kinopoisk_id=movie_data["kinopoisk_id"],
                title=movie_data["title"],
                year=movie_data["year"],
                genres=movie_data["genres"],
                description=movie_data["description"],
                poster_url=movie_data["poster_url"],
                kinopoisk_rating=movie_data["kinopoisk_rating"],
            )
            db.add(movie)
            await db.commit()

            await state.set_state(AdminMenuState.sessions_menu)
            await replace_bot_message(
                message, state,
                f"✅ Фильм <b>{movie_data['title']}</b> добавлен в слот {slot}.",
                reply_markup=_get_session_keyboard(session.status),
            )
        except Exception as e:
            logger.exception("Error adding movie to slot: %s", e)
            await abort_flow(message, state, "❌ Ошибка при добавлении фильма.")


@router.message(F.text == BTN_ADM_DEL_SLOT_MOVIE)
async def admin_del_slot_movie(message: Message, state: FSMContext) -> None:
    """Show movies in active session for deletion."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_COLLECTING:
            await replace_bot_message(
                message, state,
                "⚠️ Нет сессии в статусе «сбор предложений».",
            )
            return

        movies = await get_session_movies(db, session.id)
        if not movies:
            await replace_bot_message(
                message, state,
                "ℹ️ В сессии нет фильмов.",
                reply_markup=_get_session_keyboard(session.status),
            )
            return

        text = "🗑 <b>Выберите фильм для удаления:</b>\n\n"
        for m in movies:
            text += f"Слот {m.slot}: <b>{m.title}</b>{format_year_suffix(m.year)}\n"
            text += f"  /del_movie_{m.id}\n\n"

        await replace_bot_message(
            message, state,
            text,
            reply_markup=_get_session_keyboard(session.status),
        )


@router.message(F.text.regexp(r"^/del_movie_(\d+)$"))
async def admin_del_movie_cmd(message: Message, state: FSMContext) -> None:
    """Delete a movie from active session by inline command."""
    match = re.match(r"^/del_movie_(\d+)$", message.text)
    if not match:
        return
    movie_id = int(match.group(1))
    await try_delete_message(message)

    async with AsyncSessionLocal() as db:
        ok = await delete_movie_by_id(db, movie_id)
        if ok:
            await replace_bot_message(
                message, state,
                f"✅ Фильм (ID {movie_id}) удалён из сессии.",
            )
        else:
            await replace_bot_message(
                message, state,
                f"❌ Фильм с ID {movie_id} не найден.",
            )


# ── Session actions: voting ──────────────────────────────────────────────


@router.message(F.text == BTN_ADM_FORCE_FINISH_VOTE)
async def admin_force_finish_vote(message: Message, state: FSMContext) -> None:
    """Force finish voting and transition to rating."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_VOTING:
            await replace_bot_message(
                message, state,
                "⚠️ Нет сессии в статусе «голосование».",
            )
            return

        ok = await set_session_status(db, session, STATUS_RATING)
        if not ok:
            await replace_bot_message(message, state, "❌ Ошибка смены статуса.")
            return

        await replace_bot_message(
            message, state,
            "✅ Голосование завершено, сессия переведена в статус <b>рейтинг</b>.\n\n"
            "⚠️ Победители не определены автоматически. "
            "Назначьте победителей вручную или добавьте рейтинги.",
            reply_markup=get_admin_sessions_rating_keyboard(),
        )


@router.message(F.text == BTN_ADM_SET_WINNER)
async def admin_set_winner_start(message: Message, state: FSMContext) -> None:
    """Start setting a winner manually."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_VOTING:
            await replace_bot_message(
                message, state,
                "⚠️ Нет сессии в статусе «голосование».",
            )
            return

    await state.set_state(AdminSetWinnerState.waiting_for_slot)
    await replace_bot_message(
        message, state,
        "🏆 <b>Назначить победителя</b>\n\nВведите номер слота (1 или 2):",
        reply_markup=get_admin_back_keyboard(),
    )


@router.message(AdminSetWinnerState.waiting_for_slot)
async def admin_set_winner_slot(message: Message, state: FSMContext) -> None:
    """Handle slot selection for winner assignment."""
    if message.text == BTN_BACK:
        await _return_to_sessions(message, state)
        return

    text = message.text.strip()
    await try_delete_message(message)

    if text not in ("1", "2"):
        await replace_bot_message(message, state, "⚠️ Введите <b>1</b> или <b>2</b>:")
        return

    slot = int(text)
    await state.update_data(winner_slot=slot)

    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session:
            await abort_flow(message, state, "❌ Сессия не найдена.")
            return

        movies = await get_session_movies(db, session.id)
        slot_movies = [m for m in movies if m.slot == slot]

        if not slot_movies:
            await replace_bot_message(
                message, state,
                f"ℹ️ В слоте {slot} нет фильмов.\nВведите другой слот (1 или 2):",
            )
            return

        await state.set_state(AdminSetWinnerState.waiting_for_movie_choice)
        text = f"🏆 Фильмы в слоте {slot}:\n\n"
        for m in slot_movies:
            text += f"<b>{m.title}</b>{format_year_suffix(m.year)}\n"
            text += f"  /set_winner_{m.id}\n\n"

        await replace_bot_message(message, state, text)


@router.message(F.text.regexp(r"^/set_winner_(\d+)$"))
async def admin_set_winner_cmd(message: Message, state: FSMContext) -> None:
    """Set a movie as winner by inline command."""
    match = re.match(r"^/set_winner_(\d+)$", message.text)
    if not match:
        return

    movie_id = int(match.group(1))
    data = await state.get_data()
    slot = data.get("winner_slot")
    await try_delete_message(message)

    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        movie = await get_movie_by_id(db, movie_id)

        if not session or not movie:
            await abort_flow(message, state, "❌ Сессия или фильм не найдены.")
            return

        if slot == 1:
            session.winner_slot1_id = movie.id
        else:
            session.winner_slot2_id = movie.id
        await db.commit()

        await state.set_state(AdminMenuState.sessions_menu)
        await replace_bot_message(
            message, state,
            f"✅ Победитель слота {slot}: <b>{movie.title}</b>{format_year_suffix(movie.year)}",
            reply_markup=_get_session_keyboard(session.status),
        )


@router.message(F.text == BTN_ADM_BACK_COLLECTING)
async def admin_back_to_collecting(message: Message, state: FSMContext) -> None:
    """Roll back session from voting to collecting."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_VOTING:
            await replace_bot_message(
                message, state, "⚠️ Нет сессии в статусе «голосование».",
            )
            return

        await set_session_status(db, session, STATUS_COLLECTING)
        await replace_bot_message(
            message, state,
            "✅ Сессия возвращена в статус <b>сбор предложений</b>.",
            reply_markup=get_admin_sessions_collecting_keyboard(),
        )


# ── Session actions: rating ──────────────────────────────────────────────


@router.message(F.text == BTN_ADM_FORCE_COMPLETE)
async def admin_force_complete(message: Message, state: FSMContext) -> None:
    """Force complete the session."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_RATING:
            await replace_bot_message(
                message, state, "⚠️ Нет сессии в статусе «рейтинг».",
            )
            return

        await set_session_status(db, session, STATUS_COMPLETED)
        await state.set_state(AdminMenuState.sessions_menu)
        await replace_bot_message(
            message, state,
            "✅ Сессия завершена.",
            reply_markup=get_admin_no_session_keyboard(),
        )


@router.message(F.text == BTN_ADM_ADD_RATINGS)
async def admin_add_ratings_start(message: Message, state: FSMContext) -> None:
    """Start adding ratings for a winner movie."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_RATING:
            await replace_bot_message(
                message, state, "⚠️ Нет сессии в статусе «рейтинг».",
            )
            return

        winners = _get_winner_movies(session)
        if not winners:
            await replace_bot_message(
                message, state,
                "⚠️ У сессии нет фильмов-победителей. Назначьте победителей.",
            )
            return

        text = "📊 <b>Выберите фильм для добавления рейтингов:</b>\n\n"
        for m in winners:
            text += f"<b>{m.title}</b>{format_year_suffix(m.year)}\n"
            text += f"  /add_rating_{m.id}\n\n"

        await state.set_state(AdminAddRatingsState.waiting_for_movie_choice)
        await replace_bot_message(
            message, state, text,
            reply_markup=get_admin_back_keyboard(),
        )


@router.message(F.text.regexp(r"^/add_rating_(\d+)$"))
async def admin_add_rating_select(message: Message, state: FSMContext) -> None:
    """Select movie for rating input."""
    match = re.match(r"^/add_rating_(\d+)$", message.text)
    if not match:
        return

    movie_id = int(match.group(1))
    await try_delete_message(message)
    await state.update_data(rating_movie_id=movie_id)
    await state.set_state(AdminAddRatingsState.waiting_for_ratings)

    await replace_bot_message(
        message, state,
        "📊 Отправьте рейтинги в формате:\n"
        "<code>@username1 8\n@username2 9\nuser3 7</code>\n\n"
        "Или просто числа:\n<code>8 9 7 10 6</code>",
        reply_markup=get_admin_back_keyboard(),
    )


@router.message(AdminAddRatingsState.waiting_for_ratings)
async def admin_add_ratings_input(message: Message, state: FSMContext) -> None:
    """Handle ratings text input."""
    if message.text == BTN_BACK:
        await _return_to_sessions(message, state)
        return

    text = message.text.strip()
    await try_delete_message(message)

    data = await state.get_data()
    movie_id = data.get("rating_movie_id")

    if not movie_id:
        await abort_flow(message, state, "❌ ID фильма потерян.")
        return

    ratings = _parse_ratings_input(text)
    if not ratings:
        await replace_bot_message(
            message, state,
            "⚠️ Не удалось распознать рейтинги.\n\n"
            "Формат:\n<code>@user1 8\n@user2 9</code>\n"
            "или: <code>8 9 7 10</code>",
        )
        return

    async with AsyncSessionLocal() as db:
        try:
            movie = await get_movie_by_id(db, movie_id)
            if not movie:
                await abort_flow(message, state, "❌ Фильм не найден.")
                return

            added = await _save_ratings_batch(db, movie.session_id, movie_id, ratings)
            await db.commit()

            avg = await recalc_club_rating(db, movie_id)

            await state.set_state(AdminMenuState.sessions_menu)
            session = await _get_active_session(db, await _get_admin_group_id(state))
            avg_str = f"{avg:.2f}" if avg else "—"
            await replace_bot_message(
                message, state,
                f"✅ Добавлено {added} рейтингов.\n"
                f"Рейтинг КК: ⭐ {avg_str}",
                reply_markup=_get_session_keyboard(
                    session.status if session else STATUS_COMPLETED
                ),
            )
        except Exception as e:
            logger.exception("Error adding ratings: %s", e)
            await abort_flow(message, state, "❌ Ошибка при добавлении рейтингов.")


@router.message(F.text == BTN_ADM_BACK_VOTING)
async def admin_back_to_voting(message: Message, state: FSMContext) -> None:
    """Roll back session from rating to voting."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session or session.status != STATUS_RATING:
            await replace_bot_message(
                message, state, "⚠️ Нет сессии в статусе «рейтинг».",
            )
            return

        await set_session_status(db, session, STATUS_VOTING)
        await replace_bot_message(
            message, state,
            "✅ Сессия возвращена в статус <b>голосование</b>.",
            reply_markup=get_admin_sessions_voting_keyboard(),
        )


# ── Session actions: common ──────────────────────────────────────────────


@router.message(F.text == BTN_ADM_CANCEL_SESSION)
async def admin_cancel_session(message: Message, state: FSMContext) -> None:
    """Cancel (complete) the active session."""
    await try_delete_message(message)
    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session:
            await replace_bot_message(
                message, state, "⚠️ Нет активной сессии.",
            )
            return

        await set_session_status(db, session, STATUS_COMPLETED)
        await state.set_state(AdminMenuState.sessions_menu)
        await replace_bot_message(
            message, state,
            "✅ Сессия отменена (завершена).",
            reply_markup=get_admin_no_session_keyboard(),
        )


# ══════════════════════════════════════════════════════════════════════════
# MOVIES SUB-MENU
# ══════════════════════════════════════════════════════════════════════════


@router.message(F.text == BTN_ADMIN_MOVIES)
async def admin_movies(message: Message, state: FSMContext) -> None:
    """Show movies sub-menu."""
    await try_delete_message(message)
    await state.set_state(AdminMenuState.movies_menu)
    await replace_bot_message(
        message, state,
        "🎬 <b>Фильмы</b>\n\nВыберите действие:",
        reply_markup=get_admin_movies_keyboard(),
    )


@router.message(F.text == BTN_ADM_MOVIE_LIST)
async def admin_movie_list(message: Message, state: FSMContext) -> None:
    """Show paginated movie list with inline actions."""
    await try_delete_message(message)
    await _send_movie_list_page(message, state, page=1)


@router.callback_query(F.data.startswith("adm_movies_page:"))
async def admin_movie_list_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle movie list pagination."""
    page_str = callback.data.split(":")[1]
    if page_str == "noop":
        await callback.answer()
        return

    page = int(page_str)
    await callback.answer()

    # Delete old message and send a new one
    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_movie_list_page(callback.message, state, page)


@router.message(F.text == BTN_ADM_MOVIE_SEARCH)
async def admin_movie_search_start(message: Message, state: FSMContext) -> None:
    """Start movie search by title."""
    await try_delete_message(message)
    await state.set_state(AdminSearchMovieState.waiting_for_query)
    await replace_bot_message(
        message, state,
        "🔍 Введите название фильма для поиска:",
        reply_markup=get_admin_back_keyboard(),
    )


@router.message(AdminSearchMovieState.waiting_for_query)
async def admin_movie_search_input(message: Message, state: FSMContext) -> None:
    """Handle search query input."""
    if message.text == BTN_BACK:
        await try_delete_message(message)
        await state.set_state(AdminMenuState.movies_menu)
        await replace_bot_message(
            message, state,
            "🎬 <b>Фильмы</b>\n\nВыберите действие:",
            reply_markup=get_admin_movies_keyboard(),
        )
        return

    query = message.text.strip()
    await try_delete_message(message)

    async with AsyncSessionLocal() as db:
        movies = await search_movies_by_title(db, query)

    if not movies:
        await replace_bot_message(
            message, state,
            f"ℹ️ Ничего не найдено по запросу «{query}».\n\n"
            "Введите другое название:",
        )
        return

    await state.set_state(AdminMenuState.movies_menu)

    # Delete old bot message and send search results
    data = await state.get_data()
    old_msg_id = data.get("bot_message_id")
    if old_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, old_msg_id)
        except Exception:
            pass

    for movie in movies:
        text = _format_movie_card(movie)
        await message.answer(
            text,
            reply_markup=get_admin_movie_actions_keyboard(movie.id),
        )

    nav_msg = await message.answer(
        f"🔍 Найдено: {len(movies)}",
        reply_markup=get_admin_movies_keyboard(),
    )
    await state.update_data(bot_message_id=nav_msg.message_id)


# ── Movie inline actions ─────────────────────────────────────────────────


@router.callback_query(F.data.startswith("adm_edit_rating:"))
async def admin_edit_rating_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start editing club rating for a movie."""
    movie_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with AsyncSessionLocal() as db:
        movie = await get_movie_by_id(db, movie_id)

    if not movie:
        await callback.answer("❌ Фильм не найден", show_alert=True)
        return

    current = f"{movie.club_rating:.2f}" if movie.club_rating else "не задан"

    await state.set_state(AdminEditRatingState.waiting_for_rating)
    await state.update_data(edit_movie_id=movie_id)

    bot_msg = await callback.message.answer(
        f"✏️ <b>Изменение рейтинга</b>\n\n"
        f"🎬 {movie.title}{format_year_suffix(movie.year)}\n"
        f"Текущий рейтинг КК: ⭐ {current}\n\n"
        f"Введите новый рейтинг (от 1.00 до 10.00):",
        reply_markup=get_admin_back_keyboard(),
    )
    await state.update_data(bot_message_id=bot_msg.message_id)


@router.message(AdminEditRatingState.waiting_for_rating)
async def admin_edit_rating_input(message: Message, state: FSMContext) -> None:
    """Handle new rating value input."""
    if message.text == BTN_BACK:
        await try_delete_message(message)
        await state.set_state(AdminMenuState.movies_menu)
        await replace_bot_message(
            message, state,
            "🎬 <b>Фильмы</b>\n\nВыберите действие:",
            reply_markup=get_admin_movies_keyboard(),
        )
        return

    text = message.text.strip().replace(",", ".")
    await try_delete_message(message)

    try:
        new_rating = float(text)
    except ValueError:
        await replace_bot_message(
            message, state,
            "⚠️ Неверный формат. Введите число от 1.00 до 10.00:",
        )
        return

    if not (1.0 <= new_rating <= 10.0):
        await replace_bot_message(
            message, state,
            "⚠️ Рейтинг должен быть от 1.00 до 10.00:",
        )
        return

    data = await state.get_data()
    movie_id = data.get("edit_movie_id")

    async with AsyncSessionLocal() as db:
        try:
            movie = await get_movie_by_id(db, movie_id)
            if not movie:
                await abort_flow(message, state, "❌ Фильм не найден.")
                return

            movie.club_rating = round(new_rating, 2)
            await db.commit()

            await state.set_state(AdminMenuState.movies_menu)
            await replace_bot_message(
                message, state,
                f"✅ Рейтинг обновлён!\n\n"
                f"🎬 {movie.title}{format_year_suffix(movie.year)}\n"
                f"Новый рейтинг КК: ⭐ {movie.club_rating:.2f}",
                reply_markup=get_admin_movies_keyboard(),
            )
        except Exception as e:
            logger.exception("Error editing rating: %s", e)
            await abort_flow(message, state, "❌ Ошибка при обновлении рейтинга.")


@router.callback_query(F.data.startswith("adm_delete:"))
async def admin_delete_movie_confirm(callback: CallbackQuery, state: FSMContext) -> None:  # noqa: ARG001
    """Show deletion confirmation."""
    parts = callback.data.split(":")
    movie_id = int(parts[1])
    await callback.answer()

    async with AsyncSessionLocal() as db:
        movie = await get_movie_by_id(db, movie_id)

    if not movie:
        await callback.answer("❌ Фильм не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 <b>Удалить фильм?</b>\n\n"
        f"🎬 {movie.title}{format_year_suffix(movie.year)}\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=get_admin_delete_confirm_keyboard(movie_id),
    )


@router.callback_query(F.data.startswith("adm_delete_yes:"))
async def admin_delete_movie_yes(callback: CallbackQuery, state: FSMContext) -> None:  # noqa: ARG001
    """Confirm and delete a movie."""
    movie_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with AsyncSessionLocal() as db:
        movie = await get_movie_by_id(db, movie_id)
        title = movie.title if movie else f"ID {movie_id}"
        ok = await delete_movie_by_id(db, movie_id)

    if ok:
        await callback.message.edit_text(f"✅ Фильм <b>{title}</b> удалён.")
    else:
        await callback.message.edit_text("❌ Не удалось удалить фильм.")


@router.callback_query(F.data == "adm_delete_no")
async def admin_delete_movie_no(callback: CallbackQuery, state: FSMContext) -> None:  # noqa: ARG001
    """Cancel movie deletion."""
    await callback.answer("Отменено")
    await callback.message.delete()


# ══════════════════════════════════════════════════════════════════════════
# BATCH IMPORT
# ══════════════════════════════════════════════════════════════════════════


@router.message(F.text == BTN_ADMIN_BATCH)
async def admin_batch_start(message: Message, state: FSMContext) -> None:
    """Start batch import flow."""
    await try_delete_message(message)
    await state.set_state(AdminBatchImportState.waiting_for_data)
    await replace_bot_message(
        message, state,
        "📥 <b>Batch-импорт фильмов</b>\n\n"
        "Отправьте список фильмов (одна строка = один фильм):\n\n"
        "<code>https://www.kinopoisk.ru/film/12345/ 7.85\n"
        "https://www.kinopoisk.ru/film/67890/ 8.2\n"
        "https://www.kinopoisk.ru/film/11111/ 6.5</code>\n\n"
        "Формат строки: <code>&lt;ссылка_КП&gt; &lt;рейтинг&gt;</code>\n"
        "Рейтинг — число от 1.00 до 10.00",
        reply_markup=get_admin_back_keyboard(),
    )


@router.message(AdminBatchImportState.waiting_for_data)
async def admin_batch_data(message: Message, state: FSMContext) -> None:
    """Parse batch import data."""
    if message.text == BTN_BACK:
        await try_delete_message(message)
        await state.set_state(AdminMenuState.main_menu)
        await replace_bot_message(
            message, state,
            "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
            reply_markup=get_admin_menu_keyboard(),
        )
        return

    text = message.text.strip()
    await try_delete_message(message)

    entries = _parse_batch_import(text)
    if not entries:
        await replace_bot_message(
            message, state,
            "⚠️ Не удалось распознать данные.\n\n"
            "Формат: <code>&lt;ссылка&gt; &lt;рейтинг&gt;</code>\n"
            "Одна строка — один фильм.",
        )
        return

    # Show progress message
    await replace_bot_message(
        message, state,
        f"⏳ Загружаю данные о {len(entries)} фильмах с Кинопоиска...",
    )

    # Parse all movies from KP
    parsed: List[dict] = []
    errors: List[str] = []

    for url, rating in entries:
        try:
            movie_data = await parse_movie_data(url)
            movie_data["club_rating"] = rating
            parsed.append(movie_data)
        except KinopoiskParserError as e:
            errors.append(f"❌ {url}: {e}")

    if not parsed:
        error_text = "\n".join(errors) if errors else "Ошибка парсинга."
        await replace_bot_message(
            message, state,
            f"❌ Не удалось загрузить ни одного фильма.\n\n{error_text}",
            reply_markup=get_admin_back_keyboard(),
        )
        return

    # Build preview
    preview = "📥 <b>Превью импорта:</b>\n\n"
    for i, md in enumerate(parsed, 1):
        year_str = format_year_suffix(md.get("year"))
        preview += (
            f"{i}. <b>{md['title']}</b>{year_str} "
            f"— рейтинг КК: {md['club_rating']:.2f}\n"
        )

    if errors:
        preview += f"\n⚠️ Ошибки ({len(errors)}):\n" + "\n".join(errors[:5])

    preview += "\n\n<b>Подтвердить импорт?</b>"

    await state.update_data(batch_parsed=parsed)
    await state.set_state(AdminBatchImportState.confirm)
    await replace_bot_message(
        message, state,
        preview,
        reply_markup=get_confirmation_keyboard("batch_import"),
    )


@router.callback_query(F.data == "confirm:batch_import:yes")
async def admin_batch_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Confirm and execute batch import."""
    data = await state.get_data()
    parsed = data.get("batch_parsed", [])
    await callback.answer()

    if not parsed:
        await callback.message.edit_text("❌ Данные для импорта потеряны.")
        await state.clear()
        return

    async with AsyncSessionLocal() as db:
        try:
            group = await get_or_create_group(db, data["admin_group_id"])
            system_user = await _get_or_create_system_user(db)
            imported = 0

            for md in parsed:
                session = await create_completed_session_for_import(
                    db, group.id, system_user.id,
                )
                movie = Movie(
                    session_id=session.id,
                    user_id=system_user.id,
                    slot=1,
                    kinopoisk_url=md["kinopoisk_url"],
                    kinopoisk_id=md["kinopoisk_id"],
                    title=md["title"],
                    year=md["year"],
                    genres=md["genres"],
                    description=md["description"],
                    poster_url=md["poster_url"],
                    kinopoisk_rating=md["kinopoisk_rating"],
                    club_rating=round(md["club_rating"], 2),
                )
                db.add(movie)
                await db.flush()

                session.winner_slot1_id = movie.id
                await db.flush()
                imported += 1

            await db.commit()

            await state.set_state(AdminMenuState.main_menu)
            await callback.message.edit_text(
                f"✅ <b>Импорт завершён!</b>\n\n"
                f"Импортировано фильмов: {imported}"
            )

            await callback.message.answer(
                "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
                reply_markup=get_admin_menu_keyboard(),
            )

        except Exception as e:
            logger.exception("Batch import error: %s", e)
            await callback.message.edit_text(
                f"❌ Ошибка импорта: {e}"
            )
            await state.clear()


@router.callback_query(F.data == "confirm:batch_import:no")
async def admin_batch_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel batch import."""
    await callback.answer()
    await state.set_state(AdminMenuState.main_menu)
    await callback.message.edit_text("❌ Импорт отменён.")

    await callback.message.answer(
        "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=get_admin_menu_keyboard(),
    )


# ══════════════════════════════════════════════════════════════════════════
# DB STATS
# ══════════════════════════════════════════════════════════════════════════


@router.message(F.text == BTN_ADMIN_STATS)
async def admin_db_stats(message: Message, state: FSMContext) -> None:
    """Show database statistics."""
    await try_delete_message(message)

    async with AsyncSessionLocal() as db:
        try:
            users = (await db.execute(select(func.count(User.id)))).scalar()
            groups = (await db.execute(select(func.count(Group.id)))).scalar()
            sessions = (await db.execute(select(func.count(Session.id)))).scalar()
            movies = (await db.execute(select(func.count(Movie.id)))).scalar()
            ratings = (await db.execute(select(func.count(Rating.id)))).scalar()

            await replace_bot_message(
                message, state,
                "📊 <b>СТАТИСТИКА БАЗЫ ДАННЫХ</b>\n\n"
                f"👥 Пользователей: {users}\n"
                f"🏢 Групп: {groups}\n"
                f"📅 Сессий: {sessions}\n"
                f"🎬 Фильмов: {movies}\n"
                f"⭐ Рейтингов: {ratings}",
                reply_markup=get_admin_menu_keyboard(),
            )
        except Exception as e:
            logger.exception("Error showing DB stats: %s", e)
            await replace_bot_message(
                message, state,
                "❌ Ошибка при получении статистики.",
            )


# ══════════════════════════════════════════════════════════════════════════
# LOGS
# ══════════════════════════════════════════════════════════════════════════


@router.message(F.text == BTN_ADMIN_LOGS)
async def admin_logs(message: Message, state: FSMContext) -> None:
    """Show last 50 log entries."""
    await try_delete_message(message)

    lines = get_recent_logs(50)
    if not lines:
        await replace_bot_message(
            message, state,
            "📜 <b>Логи</b>\n\nНет записей.",
            reply_markup=get_admin_menu_keyboard(),
        )
        return

    log_text = "\n".join(lines)

    # Telegram message limit is ~4096 chars; truncate if needed
    max_len = 3800
    if len(log_text) > max_len:
        log_text = log_text[-max_len:]
        log_text = "...(обрезано)\n" + log_text

    await replace_bot_message(
        message, state,
        f"📜 <b>Последние логи:</b>\n\n<pre>{_escape_html(log_text)}</pre>",
        reply_markup=get_admin_menu_keyboard(),
    )


# ══════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════════════


async def _get_active_session(db, group_telegram_id: int) -> Optional[Session]:
    """Get any active session for the given group."""
    group = await get_or_create_group(db, group_telegram_id)
    return await get_active_session_any(db, group.id)


async def _format_session_info(db, session: Session) -> str:
    """Format session info text for the admin panel."""
    movies = await get_session_movies(db, session.id)
    status_label = session.status_obj.name if session.status_obj else session.status

    text = (
        f"📋 <b>Активная сессия #{session.id}</b>\n\n"
        f"Статус: <b>{status_label}</b>\n"
        f"Создана: {session.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Фильмов: {len(movies)}\n"
    )

    if movies:
        text += "\n"
        for m in movies:
            winner_mark = ""
            if session.winner_slot1_id == m.id or session.winner_slot2_id == m.id:
                winner_mark = " 🏆"
            text += f"  Слот {m.slot}: {m.title}{format_year_suffix(m.year)}{winner_mark}\n"

    text += "\nВыберите действие:"
    return text


def _get_session_keyboard(status: str):
    """Get the appropriate session keyboard for the given status."""
    if status == STATUS_COLLECTING:
        return get_admin_sessions_collecting_keyboard()
    elif status == STATUS_VOTING:
        return get_admin_sessions_voting_keyboard()
    elif status == STATUS_RATING:
        return get_admin_sessions_rating_keyboard()
    return get_admin_no_session_keyboard()


def _get_winner_movies(session: Session) -> List[Movie]:
    """Extract winner movies from session relationships."""
    winners = []
    if session.winner_slot1:
        winners.append(session.winner_slot1)
    if session.winner_slot2:
        winners.append(session.winner_slot2)
    return winners


async def _return_to_sessions(message: Message, state: FSMContext) -> None:
    """Return to sessions sub-menu."""
    await try_delete_message(message)
    await state.set_state(AdminMenuState.sessions_menu)

    async with AsyncSessionLocal() as db:
        session = await _get_active_session(db, await _get_admin_group_id(state))
        if not session:
            await replace_bot_message(
                message, state,
                "📋 <b>Сессии</b>\n\nНет активной сессии.",
                reply_markup=get_admin_no_session_keyboard(),
            )
            return

        text = await _format_session_info(db, session)
        await replace_bot_message(
            message, state,
            text,
            reply_markup=_get_session_keyboard(session.status),
        )


async def _send_movie_list_page(
    message: Message,
    state: FSMContext,
    page: int,
) -> None:
    """Send a page of the movie list with inline action buttons."""
    async with AsyncSessionLocal() as db:
        movies, total_pages = await get_movies_paginated(db, page, MOVIES_PER_PAGE)

        if not movies:
            await replace_bot_message(
                message, state,
                "ℹ️ Нет фильмов в базе данных.",
                reply_markup=get_admin_movies_keyboard(),
            )
            return

    # Delete old bot message
    data = await state.get_data()
    old_msg_id = data.get("bot_message_id")
    if old_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, old_msg_id)
        except Exception:
            pass

    # Send each movie as a separate message with action buttons
    for movie in movies:
        text = _format_movie_card(movie)
        await message.answer(
            text,
            reply_markup=get_admin_movie_actions_keyboard(movie.id, page),
        )

    # Send pagination + back to movies menu
    pagination = get_admin_movie_list_pagination(page, total_pages)
    nav_msg = await message.answer(
        f"📋 Страница {page}/{total_pages}",
        reply_markup=pagination,
    )
    await state.update_data(bot_message_id=nav_msg.message_id)


def _format_movie_card(movie: Movie) -> str:
    """Format a movie card for the admin movie list."""
    year_str = format_year_suffix(movie.year)
    kp_rating = f"{movie.kinopoisk_rating:.1f}" if movie.kinopoisk_rating else "—"
    club = f"{movie.club_rating:.2f}" if movie.club_rating else "—"
    return (
        f"🎬 <b>{movie.title}</b>{year_str}\n"
        f"⭐ КК: {club} | КП: {kp_rating}\n"
        f"Сессия: {movie.session_id} | Слот: {movie.slot}"
    )


def _parse_batch_import(text: str) -> List[Tuple[str, float]]:
    """Parse batch import text into list of (url, club_rating)."""
    entries: List[Tuple[str, float]] = []

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue

        url, rating_str = parts
        rating_str = rating_str.replace(",", ".")

        try:
            rating = float(rating_str)
            if not (1.0 <= rating <= 10.0):
                continue
        except ValueError:
            continue

        if "kinopoisk" not in url.lower():
            continue

        entries.append((url, rating))

    return entries


def _parse_ratings_input(text: str) -> List[Tuple[Optional[str], int]]:
    """Parse ratings input text into list of (username_or_none, rating)."""
    ratings: List[Tuple[Optional[str], int]] = []

    for line in text.split("\n"):
        parts = line.strip().split()
        if len(parts) == 2:
            username, rating_str = parts
            try:
                rating = int(rating_str)
                if 1 <= rating <= 10:
                    ratings.append((username.lstrip("@"), rating))
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


async def _save_ratings_batch(
    db,
    session_id: int,
    movie_id: int,
    ratings: List[Tuple[Optional[str], int]],
) -> int:
    """Save a batch of ratings, creating placeholder users as needed."""
    from bot.database.repositories import get_user_by_username

    added = 0
    for username, rating in ratings:
        user = None
        if username:
            user = await get_user_by_username(db, username)

        if not user:
            user = User(
                telegram_id=0,
                username=username or f"User{added}",
                first_name=username or f"User{added}",
            )
            db.add(user)
            await db.flush()

        db.add(Rating(
            session_id=session_id,
            movie_id=movie_id,
            user_id=user.id,
            rating=rating,
        ))
        added += 1

    return added


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
