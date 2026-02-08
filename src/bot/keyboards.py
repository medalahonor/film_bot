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
