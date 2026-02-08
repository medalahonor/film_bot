"""Keyboards for the bot (inline + reply)."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ── Reply keyboard button labels ─────────────────────────────────────────

# Session management
BTN_NEW_SESSION = "🎬 Новая сессия"
BTN_STATUS = "📋 Статус"
BTN_CANCEL_SESSION = "❌ Отменить сессию"

# Voting
BTN_START_VOTING = "🗳 Начать голосование"
BTN_FINISH_VOTING = "🏁 Завершить голосование"
BTN_REVOTE = "🔄 Переголосование"

# Rating
BTN_RATE = "⭐ Оценить фильмы"
BTN_COMPLETE_SESSION = "✅ Завершить сессию"

# Info
BTN_LEADERBOARD = "🏆 Лидерборд"
BTN_SEARCH = "🔍 Поиск"
BTN_STATS = "📊 Статистика"
BTN_HELP = "❓ Помощь"

# Proposals
BTN_PROPOSE = "📝 Предложить фильм"

# Sub-keyboard buttons
BTN_SLOT_1 = "📍 Слот 1"
BTN_SLOT_2 = "📍 Слот 2"
BTN_CANCEL = "↩️ Отмена"
BTN_BACK = "↩️ Назад"

# Admin panel
BTN_ADMIN_SESSIONS = "📋 Сессии"
BTN_ADMIN_MOVIES = "🎬 Фильмы (админ)"
BTN_ADMIN_BATCH = "📥 Batch-импорт"
BTN_ADMIN_STATS = "📊 Статистика БД"
BTN_ADMIN_LOGS = "📜 Логи"
BTN_ADMIN_EXIT = "↩️ Выход из панели"

# Admin sessions
BTN_ADM_FORCE_VOTING = "➡️ Начать голосование"
BTN_ADM_ADD_MOVIE = "🎬 Добавить фильм в слот"
BTN_ADM_DEL_SLOT_MOVIE = "🗑 Удалить фильм из слота"
BTN_ADM_CANCEL_SESSION = "❌ Отменить сессию"
BTN_ADM_FORCE_FINISH_VOTE = "🏁 Завершить голосование"
BTN_ADM_SET_WINNER = "🏆 Назначить победителя"
BTN_ADM_BACK_COLLECTING = "⏪ Вернуть на сбор"
BTN_ADM_FORCE_COMPLETE = "✅ Завершить сессию"
BTN_ADM_ADD_RATINGS = "📊 Добавить рейтинги"
BTN_ADM_BACK_VOTING = "⏪ Вернуть на голосование"

# Admin movies
BTN_ADM_MOVIE_LIST = "📋 Список фильмов"
BTN_ADM_MOVIE_SEARCH = "🔍 Найти фильм"


# ── Reply keyboards ──────────────────────────────────────────────────────

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get the main menu reply keyboard.

    Layout:
        Row 1: Новая сессия | Предложить фильм | Статус
        Row 2: Начать голосование | Завершить голосование | Переголосование
        Row 3: Оценить фильмы | Завершить сессию | Отменить сессию
        Row 4: Лидерборд | Поиск | Статистика
        Row 5: Помощь
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_NEW_SESSION)
    builder.button(text=BTN_PROPOSE)
    builder.button(text=BTN_STATUS)
    builder.button(text=BTN_START_VOTING)
    builder.button(text=BTN_FINISH_VOTING)
    builder.button(text=BTN_REVOTE)
    builder.button(text=BTN_RATE)
    builder.button(text=BTN_COMPLETE_SESSION)
    builder.button(text=BTN_CANCEL_SESSION)
    builder.button(text=BTN_LEADERBOARD)
    builder.button(text=BTN_SEARCH)
    builder.button(text=BTN_STATS)
    builder.button(text=BTN_HELP)
    builder.adjust(3, 3, 3, 3, 1)
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard with only the cancel button (for FSM flows)."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_CANCEL)
    return builder.as_markup(resize_keyboard=True)


def get_revote_slot_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard for revote slot selection.

    Layout:
        Row 1: Слот 1 | Слот 2
        Row 2: Отмена
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_SLOT_1)
    builder.button(text=BTN_SLOT_2)
    builder.button(text=BTN_CANCEL)
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


# ── Inline keyboards ─────────────────────────────────────────────────────

def get_slot_selection_keyboard(telegram_user_id: int) -> InlineKeyboardMarkup:
    """Get inline keyboard for slot selection (1 or 2).

    Encodes telegram_user_id into callback_data so only the
    user who proposed the film can press the button.

    Args:
        telegram_user_id: Telegram user ID of the proposer
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📍 Слот 1",
        callback_data=f"slot:1:{telegram_user_id}",
    )
    builder.button(
        text="📍 Слот 2",
        callback_data=f"slot:2:{telegram_user_id}",
    )
    builder.adjust(2)
    return builder.as_markup()


def get_rating_keyboard(movie_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for rating selection (1-10).

    Args:
        movie_id: Database movie ID for callback data
    """
    builder = InlineKeyboardBuilder()
    for rating in range(1, 11):
        builder.button(
            text=str(rating),
            callback_data=f"rate:{movie_id}:{rating}"
        )
    builder.adjust(5)  # 5 buttons per row
    return builder.as_markup()


def get_leaderboard_pagination_keyboard(
    current_page: int,
    total_pages: int
) -> InlineKeyboardMarkup:
    """Get pagination keyboard for leaderboard.

    Args:
        current_page: Current page number (1-indexed)
        total_pages: Total number of pages
    """
    builder = InlineKeyboardBuilder()

    # Previous button
    if current_page > 1:
        builder.button(text="◀️ Назад", callback_data=f"lb_page:{current_page - 1}")

    # Page numbers (show up to 5 pages)
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, start_page + 4)
    start_page = max(1, end_page - 4)

    for page in range(start_page, end_page + 1):
        if page == current_page:
            builder.button(text=f"• {page} •", callback_data=f"lb_page:{page}")
        else:
            builder.button(text=str(page), callback_data=f"lb_page:{page}")

    # Next button
    if current_page < total_pages:
        builder.button(text="Далее ▶️", callback_data=f"lb_page:{current_page + 1}")

    # Adjust layout
    if current_page > 1 and current_page < total_pages:
        # Has both prev and next
        builder.adjust(1, min(5, end_page - start_page + 1), 1)
    elif current_page > 1 or current_page < total_pages:
        # Has only prev or next
        builder.adjust(min(5, end_page - start_page + 1), 1)
    else:
        # Only page numbers
        builder.adjust(min(5, end_page - start_page + 1))

    # Add search button on new row
    builder.row(InlineKeyboardButton(text="🔍 Поиск", callback_data="lb_search"))

    return builder.as_markup()


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Get confirmation keyboard (Yes/No).

    Args:
        action: Action identifier for callback data
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=f"confirm:{action}:yes")
    builder.button(text="❌ Нет", callback_data=f"confirm:{action}:no")
    builder.adjust(2)
    return builder.as_markup()


# ── Admin keyboards ──────────────────────────────────────────────────────


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main admin panel keyboard.

    Layout:
        Row 1: Сессии | Фильмы (админ)
        Row 2: Batch-импорт | Статистика БД
        Row 3: Логи
        Row 4: Выход из панели
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADMIN_SESSIONS)
    builder.button(text=BTN_ADMIN_MOVIES)
    builder.button(text=BTN_ADMIN_BATCH)
    builder.button(text=BTN_ADMIN_STATS)
    builder.button(text=BTN_ADMIN_LOGS)
    builder.button(text=BTN_ADMIN_EXIT)
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_sessions_collecting_keyboard() -> ReplyKeyboardMarkup:
    """Admin session keyboard for 'collecting' status."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADM_FORCE_VOTING)
    builder.button(text=BTN_ADM_ADD_MOVIE)
    builder.button(text=BTN_ADM_DEL_SLOT_MOVIE)
    builder.button(text=BTN_ADM_CANCEL_SESSION)
    builder.button(text=BTN_BACK)
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_sessions_voting_keyboard() -> ReplyKeyboardMarkup:
    """Admin session keyboard for 'voting' status."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADM_FORCE_FINISH_VOTE)
    builder.button(text=BTN_ADM_SET_WINNER)
    builder.button(text=BTN_ADM_BACK_COLLECTING)
    builder.button(text=BTN_ADM_CANCEL_SESSION)
    builder.button(text=BTN_BACK)
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_sessions_rating_keyboard() -> ReplyKeyboardMarkup:
    """Admin session keyboard for 'rating' status."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADM_FORCE_COMPLETE)
    builder.button(text=BTN_ADM_ADD_RATINGS)
    builder.button(text=BTN_ADM_BACK_VOTING)
    builder.button(text=BTN_ADM_CANCEL_SESSION)
    builder.button(text=BTN_BACK)
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_no_session_keyboard() -> ReplyKeyboardMarkup:
    """Admin keyboard when no active session exists."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_BACK)
    return builder.as_markup(resize_keyboard=True)


def get_admin_movies_keyboard() -> ReplyKeyboardMarkup:
    """Admin movies submenu keyboard.

    Layout:
        Row 1: Список фильмов | Найти фильм
        Row 2: Назад
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADM_MOVIE_LIST)
    builder.button(text=BTN_ADM_MOVIE_SEARCH)
    builder.button(text=BTN_BACK)
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_back_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with only the back button."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_BACK)
    return builder.as_markup(resize_keyboard=True)


def get_admin_movie_actions_keyboard(
    movie_id: int,
    page: int = 1,
) -> InlineKeyboardMarkup:
    """Inline actions for a single movie in admin list."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✏️ Рейтинг",
        callback_data=f"adm_edit_rating:{movie_id}",
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=f"adm_delete:{movie_id}:{page}",
    )
    builder.adjust(2)
    return builder.as_markup()


def get_admin_movie_list_pagination(
    current_page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Pagination keyboard for admin movie list."""
    builder = InlineKeyboardBuilder()
    if current_page > 1:
        builder.button(
            text="◀️ Назад",
            callback_data=f"adm_movies_page:{current_page - 1}",
        )
    builder.button(
        text=f"{current_page}/{total_pages}",
        callback_data="adm_movies_page:noop",
    )
    if current_page < total_pages:
        builder.button(
            text="Далее ▶️",
            callback_data=f"adm_movies_page:{current_page + 1}",
        )
    return builder.as_markup()


def get_admin_delete_confirm_keyboard(movie_id: int) -> InlineKeyboardMarkup:
    """Confirmation inline keyboard for movie deletion."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"adm_delete_yes:{movie_id}")
    builder.button(text="❌ Нет", callback_data="adm_delete_no")
    builder.adjust(2)
    return builder.as_markup()
