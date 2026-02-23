"""Session handler — /start and /help only.

All film-club functionality is now in the WebApp (React + FastAPI).
The bot's role is limited to: sending the WebApp link and answering /help.
"""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import config
from bot.keyboards import get_group_open_keyboard, get_webapp_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Send welcome message with the WebApp button (private) or a link (group)."""
    logger.info("User %s called /start in chat %s", message.from_user.id, message.chat.id)

    if message.chat.type != "private":
        await message.answer(
            "🎬 <b>Киноклуб</b>\n\nНажмите кнопку, чтобы открыть приложение.",
            reply_markup=get_group_open_keyboard(),
            parse_mode="HTML",
        )
        return

    if config.WEBAPP_URL:
        await message.answer(
            "🎬 <b>Добро пожаловать в Киноклуб!</b>\n\n"
            "Нажмите кнопку ниже, чтобы открыть приложение.",
            reply_markup=get_webapp_keyboard(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "🎬 <b>Добро пожаловать в Киноклуб!</b>\n\n"
            "Приложение недоступно. Обратитесь к администратору.",
            parse_mode="HTML",
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Send brief help text."""
    webapp_hint = (
        f"\n\nОткрыть приложение: <a href='{config.WEBAPP_URL}'>Киноклуб WebApp</a>"
        if config.WEBAPP_URL
        else ""
    )
    await message.answer(
        "🎬 <b>Бот киноклуба</b>\n\n"
        "Все функции доступны через WebApp:\n"
        "• Предложить фильм или сериал\n"
        "• Проголосовать за кандидатов\n"
        "• Выставить оценку\n"
        "• Лидерборд и статистика"
        + webapp_hint
    )
