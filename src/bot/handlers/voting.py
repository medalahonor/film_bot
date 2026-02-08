"""Voting handlers."""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message, PollAnswer
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, or_, delete

from bot.database.models import Session, Movie, Vote
from bot.database.session import AsyncSessionLocal
from bot.database.status_manager import (
    get_status_by_code,
    STATUS_COLLECTING,
    STATUS_VOTING,
    STATUS_RATING,
)
from bot.database.repositories import (
    get_group_by_telegram_id,
    get_active_session,
    get_or_create_user,
)
from bot.formatters import format_year_suffix, format_user_display_name
from bot.services.voting_logic import determine_winner
from bot.keyboards import (
    BTN_START_VOTING, BTN_FINISH_VOTING, BTN_REVOTE, BTN_RATE,
    get_main_menu_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()


# ── Slot attribute mapping ────────────────────────────────────────────────

SLOT_ATTRS = {
    1: {
        "message_id": "poll_slot1_message_id",
        "poll_id": "poll_slot1_id",
        "movie_ids": "poll_slot1_movie_ids",
        "winner_id": "winner_slot1_id",
    },
    2: {
        "message_id": "poll_slot2_message_id",
        "poll_id": "poll_slot2_id",
        "movie_ids": "poll_slot2_movie_ids",
        "winner_id": "winner_slot2_id",
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────


def _serialize_movie_ids(movies: List) -> str:
    """Serialize a list of Movie objects to a JSON string of IDs."""
    return json.dumps([m.id for m in movies])


def _deserialize_movie_ids(raw: Optional[str]) -> List[int]:
    """Deserialize a JSON string of movie IDs back to a list."""
    if not raw:
        return []
    return json.loads(raw)


def _get_proposer_name(movie: Movie) -> str:
    """Return a display name for the movie proposer via relationship."""
    return format_user_display_name(
        movie.proposer.username, movie.proposer.first_name,
    )


async def _create_poll_for_movies(
    message: Message,
    movies: List[Movie],
    question: str,
    allows_multiple: bool = True,
) -> Message:
    """Create a Telegram poll for the given movies and return the poll Message."""
    options = [
        f"{movie.title}{format_year_suffix(movie.year)} — {_get_proposer_name(movie)}"
        for movie in movies
    ]
    return await message.answer_poll(
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=allows_multiple,
    )


def _set_slot_poll(session: Session, slot_num: int, poll_msg: Message, movies: List) -> None:
    """Write poll message_id, poll_id, and movie_ids into the session."""
    attrs = SLOT_ATTRS[slot_num]
    setattr(session, attrs["message_id"], poll_msg.message_id)
    setattr(session, attrs["poll_id"], poll_msg.poll.id)
    setattr(session, attrs["movie_ids"], _serialize_movie_ids(movies))


def _clear_slot_poll(session: Session, slot_num: int) -> None:
    """Clear poll references for a resolved slot."""
    attrs = SLOT_ATTRS[slot_num]
    setattr(session, attrs["message_id"], None)
    setattr(session, attrs["poll_id"], None)
    setattr(session, attrs["movie_ids"], None)


def _get_slot_attr(session: Session, slot_num: int, key: str):
    """Get a slot attribute value from the session."""
    return getattr(session, SLOT_ATTRS[slot_num][key])


async def _create_and_pin_polls(
    message: Message,
    session: Session,
    polls_to_create: Dict[int, List[Movie]],
    allows_multiple: bool = True,
    question_prefix: str = "🎬",
) -> List[Message]:
    """Create polls for the given slots, store refs in session, and pin them.

    Returns the list of created poll messages.
    """
    created_polls: List[Message] = []
    for slot_num, movies in sorted(polls_to_create.items()):
        poll = await _create_poll_for_movies(
            message, movies,
            question=f"{question_prefix} Слот {slot_num}: "
                     f"{'Выберите фильм(ы)' if allows_multiple else 'Переголосование!'}",
            allows_multiple=allows_multiple,
        )
        _set_slot_poll(session, slot_num, poll, movies)
        created_polls.append(poll)

    for poll_msg in created_polls:
        try:
            await poll_msg.pin(disable_notification=True)
        except Exception as e:
            logger.warning("Failed to pin poll: %s", e)

    return created_polls


# ── Handlers ─────────────────────────────────────────────────────────────


@router.message(F.text == BTN_START_VOTING)
async def start_voting(message: Message, state: FSMContext) -> None:
    """Start voting for collected movie proposals via reply keyboard button."""
    await state.clear()
    async with AsyncSessionLocal() as db:
        try:
            group = await get_group_by_telegram_id(db, message.chat.id)
            if not group:
                await message.answer("ℹ️ Группа не найдена.")
                return

            session = await get_active_session(db, group.id, STATUS_COLLECTING)
            if not session:
                await message.answer(
                    "⚠️ Нет активной сессии в статусе 'сбор предложений'."
                )
                return

            slot_movies = await _load_slot_movies(db, session)
            total_movies = sum(len(m) for m in slot_movies.values())

            if total_movies < 1:
                await message.answer(
                    "⚠️ Нет фильмов для голосования!\n\n"
                    "Предложите хотя бы один фильм."
                )
                return

            auto_msgs, polls_to_create = _classify_slots(session, slot_movies)

            # If no polls needed — go directly to rating
            if not polls_to_create:
                await _transition_to_status(db, session, STATUS_RATING)
                response = _format_auto_results(auto_msgs)
                await message.answer(response)
                logger.info("Session %s auto-resolved, no voting needed", session.id)
                return

            # Create and pin polls
            await _create_and_pin_polls(message, session, polls_to_create)

            # Transition to voting
            await _transition_to_status(db, session, STATUS_VOTING)
            session.voting_started_at = datetime.utcnow()
            await db.commit()

            # Unpin collection message
            await _try_unpin(message, session.pinned_message_id)

            # Send confirmation
            confirmation = "✅ Голосование началось!\n\n"
            if auto_msgs:
                confirmation += "\n".join(auto_msgs) + "\n\n"
            confirmation += (
                "Проголосуйте за фильмы выше. Можно выбрать несколько вариантов.\n"
                "Когда все проголосуют, нажмите «🏁 Завершить голосование»."
            )
            await message.answer(confirmation)

            logger.info("Voting started for session %s", session.id)

        except Exception as e:
            logger.exception("Error starting voting: %s", e)
            await message.answer("❌ Произошла ошибка при запуске голосования.")


@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer) -> None:
    """Handle poll answers to track votes in database."""
    poll_id = poll_answer.poll_id
    telegram_user = poll_answer.user
    option_ids = poll_answer.option_ids

    logger.info(
        "Poll answer from user %s: poll=%s, options=%s",
        telegram_user.id, poll_id, option_ids,
    )

    async with AsyncSessionLocal() as db:
        try:
            session = await _find_session_by_poll(db, poll_id)
            if not session:
                logger.warning("No session found for poll_id=%s", poll_id)
                return

            slot = 1 if session.poll_slot1_id == poll_id else 2

            user = await get_or_create_user(
                db, telegram_user.id, telegram_user.username,
                telegram_user.first_name, telegram_user.last_name,
            )

            poll_movie_ids = _deserialize_movie_ids(
                _get_slot_attr(session, slot, "movie_ids")
            )
            if not poll_movie_ids:
                logger.warning(
                    "No movie IDs mapping for session %s slot %d",
                    session.id, slot,
                )
                return

            ordered_movies = await _load_movies_by_ids(db, poll_movie_ids)

            # Delete existing votes for this user for ALL movies in current poll
            await db.execute(
                delete(Vote).where(
                    Vote.session_id == session.id,
                    Vote.user_id == user.id,
                    Vote.movie_id.in_(poll_movie_ids),
                )
            )

            # Create new votes for selected options
            for option_idx in option_ids:
                if option_idx < len(ordered_movies):
                    movie = ordered_movies[option_idx]
                    db.add(Vote(
                        session_id=session.id,
                        movie_id=movie.id,
                        user_id=user.id,
                    ))

            await db.commit()

            logger.info(
                "Saved %d vote(s) for user %s in session %s slot %d",
                len(option_ids), telegram_user.id, session.id, slot,
            )
        except Exception as e:
            logger.exception("Error handling poll answer: %s", e)


@router.message(F.text == BTN_FINISH_VOTING)
async def finish_voting(message: Message, state: FSMContext) -> None:
    """Finish voting and determine winners.

    Stops active polls and evaluates results.  When a slot ends in a
    tie, the tied candidates are saved and the user is prompted to
    press «Переголосование».
    """
    await state.clear()
    async with AsyncSessionLocal() as db:
        try:
            group = await get_group_by_telegram_id(db, message.chat.id)
            if not group:
                await message.answer("ℹ️ Группа не найдена.")
                return

            session = await get_active_session(db, group.id, STATUS_VOTING)
            if not session:
                await message.answer(
                    "⚠️ Нет активной сессии в статусе 'голосование'."
                )
                return

            all_movies = await _load_all_session_movies(db, session)
            movies_by_id = {m.id: m for m in all_movies}

            response = "🏆 <b>РЕЗУЛЬТАТЫ ГОЛОСОВАНИЯ</b>\n\n"
            has_any_tie = False

            for slot_num in (1, 2):
                slot_movies = [m for m in all_movies if m.slot == slot_num]
                if not slot_movies:
                    continue

                slot_text, is_tie = await _process_slot_result(
                    message, db, session, slot_num, slot_movies, movies_by_id,
                )
                response += slot_text
                if is_tie:
                    has_any_tie = True

            # Transition to rating only when all slots are resolved
            if not has_any_tie:
                await _transition_to_status(db, session, STATUS_RATING)
                response += (
                    "\n🍿 Приятного просмотра!\n"
                    "После просмотра нажмите «⭐ Оценить фильмы»."
                )
            else:
                response += (
                    "\n🔄 Нажмите «🔄 Переголосование» для запуска "
                    "нового опроса по нерешённым слотам."
                )

            await db.commit()
            await message.answer(response)

            logger.info("Voting finished for session %s", session.id)

        except Exception as e:
            logger.exception("Error finishing voting: %s", e)
            await message.answer(
                "❌ Произошла ошибка при завершении голосования."
            )


@router.message(F.text == BTN_REVOTE)
async def revote_button(message: Message, state: FSMContext) -> None:
    """Create revote polls for all unresolved slots.

    A slot is unresolved when ``poll_slot{N}_movie_ids`` is set (tied
    candidates) but there is no active poll and no winner yet.
    """
    await state.clear()
    async with AsyncSessionLocal() as db:
        try:
            group = await get_group_by_telegram_id(db, message.chat.id)
            if not group:
                await message.answer("ℹ️ Группа не найдена.")
                return

            session = await get_active_session(db, group.id, STATUS_VOTING)
            if not session:
                await message.answer(
                    "⚠️ Нет активной сессии в статусе 'голосование'."
                )
                return

            polls_to_create = await _collect_revote_slots(db, session)

            if not polls_to_create:
                await message.answer(
                    "ℹ️ Нет слотов, требующих переголосования.\n"
                    "Сначала нажмите «🏁 Завершить голосование».",
                    reply_markup=get_main_menu_keyboard(),
                )
                return

            await _create_and_pin_polls(
                message, session, polls_to_create,
                allows_multiple=False,
                question_prefix="🔄",
            )
            await db.commit()

            slots_str = ", ".join(str(s) for s in sorted(polls_to_create))
            await message.answer(
                f"🔄 Переголосование запущено для слотов: {slots_str}.\n\n"
                f"В этот раз можно выбрать только <b>один</b> вариант.\n"
                f"Когда все проголосуют, нажмите «🏁 Завершить голосование».",
            )

            logger.info(
                "Revote started for session %s slots %s",
                session.id, list(polls_to_create.keys()),
            )

        except Exception as e:
            logger.exception("Error starting revote: %s", e)
            await message.answer(
                "❌ Произошла ошибка при запуске переголосования."
            )


# ── Private helpers ──────────────────────────────────────────────────────


async def _load_slot_movies(
    db, session: Session,
) -> Dict[int, List[Movie]]:
    """Load all movies for a session grouped by slot."""
    result = await db.execute(
        select(Movie)
        .where(Movie.session_id == session.id)
        .order_by(Movie.slot, Movie.created_at)
    )
    all_movies = result.scalars().all()
    return {
        slot: [m for m in all_movies if m.slot == slot]
        for slot in (1, 2)
    }


async def _load_all_session_movies(db, session: Session) -> List[Movie]:
    """Load all movies for a session ordered by slot."""
    result = await db.execute(
        select(Movie)
        .where(Movie.session_id == session.id)
        .order_by(Movie.slot, Movie.created_at)
    )
    return list(result.scalars().all())


async def _load_movies_by_ids(
    db, movie_ids: List[int],
) -> List[Movie]:
    """Load movies by IDs preserving the order of movie_ids."""
    result = await db.execute(
        select(Movie).where(Movie.id.in_(movie_ids))
    )
    movies_by_id = {m.id: m for m in result.scalars().all()}
    return [movies_by_id[mid] for mid in movie_ids if mid in movies_by_id]


async def _find_session_by_poll(db, poll_id: str) -> Optional[Session]:
    """Find the session that owns the given Telegram poll."""
    result = await db.execute(
        select(Session).where(
            or_(
                Session.poll_slot1_id == poll_id,
                Session.poll_slot2_id == poll_id,
            )
        )
    )
    return result.scalar_one_or_none()


def _classify_slots(
    session: Session,
    slot_movies: Dict[int, List[Movie]],
) -> Tuple[List[str], Dict[int, List[Movie]]]:
    """Classify slots into auto-winners and poll-needed.

    Returns:
        (auto_winner_messages, polls_to_create)
    """
    auto_winner_messages: List[str] = []
    polls_to_create: Dict[int, List[Movie]] = {}

    for slot_num in (1, 2):
        movies = slot_movies.get(slot_num, [])
        winner_attr = SLOT_ATTRS[slot_num]["winner_id"]

        if len(movies) >= 2:
            polls_to_create[slot_num] = movies
        elif len(movies) == 1:
            setattr(session, winner_attr, movies[0].id)
            title = movies[0].title + format_year_suffix(movies[0].year)
            auto_winner_messages.append(
                f"📍 <b>Слот {slot_num}:</b> {title} "
                f"— единственный кандидат, автопобеда! 🎉"
            )

    return auto_winner_messages, polls_to_create


def _format_auto_results(auto_msgs: List[str]) -> str:
    """Format the response when all slots are auto-resolved."""
    response = "🏆 <b>РЕЗУЛЬТАТЫ</b>\n\n"
    response += "\n".join(auto_msgs)
    response += "\n\n🍿 Приятного просмотра!\n"
    response += f"После просмотра нажмите «{BTN_RATE}» для оценки фильмов."
    return response


async def _transition_to_status(db, session: Session, status_code: str) -> None:
    """Change session status and commit."""
    status = await get_status_by_code(db, status_code)
    if status:
        session.status_id = status.id
    await db.commit()


async def _try_unpin(message: Message, pinned_message_id: Optional[int]) -> None:
    """Try to unpin a message, silently ignoring errors."""
    if not pinned_message_id:
        return
    try:
        await message.bot.unpin_chat_message(
            chat_id=message.chat.id,
            message_id=pinned_message_id,
        )
    except Exception as e:
        logger.warning("Failed to unpin message: %s", e)


async def _process_slot_result(
    message: Message,
    db,
    session: Session,
    slot_num: int,
    slot_movies: List[Movie],
    movies_by_id: Dict[int, Movie],
) -> Tuple[str, bool]:
    """Process one slot's voting result.

    Returns (response_text, is_tie).
    """
    attrs = SLOT_ATTRS[slot_num]
    poll_message_id = getattr(session, attrs["message_id"])
    existing_winner_id = getattr(session, attrs["winner_id"])
    pending_movie_ids = _deserialize_movie_ids(getattr(session, attrs["movie_ids"]))

    header = f"<b>📍 Слот {slot_num}:</b>\n"

    if poll_message_id:
        slot_text, is_tie = await _resolve_poll(
            message, db, session, slot_num, slot_movies, movies_by_id,
        )
        return header + slot_text + "\n", is_tie

    if existing_winner_id:
        movie = movies_by_id.get(existing_winner_id)
        if movie:
            title = movie.title + format_year_suffix(movie.year)
            proposer = _get_proposer_name(movie)
            return header + f"🎬 {title} — победитель\nПредложил: {proposer}\n\n", False

    if pending_movie_ids:
        text = header + "⚠️ Ожидается переголосование.\n"
        for mid in pending_movie_ids:
            movie = movies_by_id.get(mid)
            if movie:
                text += f"• {movie.title}{format_year_suffix(movie.year)}\n"
        return text + "\n", True

    # Single film — auto-winner (set in start_voting)
    movie = slot_movies[0]
    title = movie.title + format_year_suffix(movie.year)
    return header + f"🎬 {title} — автопобеда (единственный кандидат)\n\n", False


async def _resolve_poll(
    message: Message,
    db,
    session: Session,
    slot_num: int,
    slot_movies: List[Movie],
    movies_by_id: Dict[int, Movie],
) -> Tuple[str, bool]:
    """Stop a slot's poll, evaluate results, and report ties.

    Returns (response_text, is_tie).
    """
    attrs = SLOT_ATTRS[slot_num]
    poll_message_id = getattr(session, attrs["message_id"])

    try:
        poll_result = await message.bot.stop_poll(
            chat_id=message.chat.id,
            message_id=poll_message_id,
        )
    except Exception as e:
        logger.error("Error stopping poll for slot %d: %s", slot_num, e)
        return "❌ Не удалось остановить опрос.\n", False

    poll_movie_ids = _deserialize_movie_ids(getattr(session, attrs["movie_ids"]))
    vote_counts = _extract_vote_counts(poll_result, poll_movie_ids)

    winners, is_tie = determine_winner(vote_counts)
    text = ""

    if is_tie:
        text = _format_tie_result(winners, movies_by_id, vote_counts)
        await _clear_votes_for_slot(db, session, slot_movies)
        # Keep only tied movie IDs for the revote handler
        tied_movies = [movies_by_id[mid] for mid in winners if mid in movies_by_id]
        setattr(session, attrs["message_id"], None)
        setattr(session, attrs["poll_id"], None)
        setattr(session, attrs["movie_ids"], _serialize_movie_ids(tied_movies))
        return text, True

    if winners:
        winner_id = winners[0]
        movie = movies_by_id.get(winner_id)
        votes = vote_counts.get(winner_id, 0)
        text = _format_winner_result(movie, votes)
        setattr(session, attrs["winner_id"], winner_id)
        _clear_slot_poll(session, slot_num)

    return text, False


def _extract_vote_counts(poll_result, poll_movie_ids: List[int]) -> Dict[int, int]:
    """Map poll options to movie IDs with vote counts."""
    vote_counts: Dict[int, int] = {}
    for idx, movie_id in enumerate(poll_movie_ids):
        if idx < len(poll_result.options):
            vote_counts[movie_id] = poll_result.options[idx].voter_count
    return vote_counts


def _format_tie_result(
    tied_ids: List[int],
    movies_by_id: Dict[int, Movie],
    vote_counts: Dict[int, int],
) -> str:
    """Format tie result text."""
    text = "⚠️ Ничья! Необходимо переголосование.\n"
    for mid in tied_ids:
        movie = movies_by_id.get(mid)
        if movie:
            votes = vote_counts.get(movie.id, 0)
            text += f"• {movie.title}{format_year_suffix(movie.year)} — {votes} голосов\n"
    return text


def _format_winner_result(movie: Optional[Movie], votes: int) -> str:
    """Format single winner result text."""
    if not movie:
        return ""
    title = movie.title + format_year_suffix(movie.year)
    proposer = _get_proposer_name(movie)
    if votes == 0:
        return f"🎲 {title} — выбран случайно (нет голосов)\nПредложил: {proposer}\n"
    return f"🎬 {title} — {votes} голосов\nПредложил: {proposer}\n"


async def _clear_votes_for_slot(db, session: Session, slot_movies: List[Movie]) -> None:
    """Delete all votes for movies in a slot."""
    slot_movie_ids = [m.id for m in slot_movies]
    if slot_movie_ids:
        await db.execute(
            delete(Vote).where(
                Vote.session_id == session.id,
                Vote.movie_id.in_(slot_movie_ids),
            )
        )


async def _collect_revote_slots(
    db, session: Session,
) -> Dict[int, List[Movie]]:
    """Determine which slots need a revote and return them with their movies.

    A slot needs revote when it has tied candidates (movie_ids set)
    but no active poll and no winner.
    """
    polls_to_create: Dict[int, List[Movie]] = {}

    for slot_num in (1, 2):
        attrs = SLOT_ATTRS[slot_num]
        poll_message_id = getattr(session, attrs["message_id"])
        winner_id = getattr(session, attrs["winner_id"])
        pending_ids = _deserialize_movie_ids(getattr(session, attrs["movie_ids"]))

        if not pending_ids or poll_message_id or winner_id:
            continue

        tied_movies = await _load_movies_by_ids(db, pending_ids)

        if len(tied_movies) < 2:
            # Only one movie left — auto-win
            if tied_movies:
                setattr(session, attrs["winner_id"], tied_movies[0].id)
                _clear_slot_poll(session, slot_num)
            continue

        polls_to_create[slot_num] = tied_movies

    return polls_to_create
