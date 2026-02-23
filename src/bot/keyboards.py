"""Keyboards for the bot.

All complex UI is now in the WebApp (React + FastAPI).
The bot only needs a single inline button that opens the WebApp.
"""
from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import config


def get_webapp_keyboard(webapp_url: str = "") -> InlineKeyboardMarkup:
    """Inline keyboard with a single WebApp button."""
    url = webapp_url or config.WEBAPP_URL
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Открыть киноклуб", web_app=WebAppInfo(url=url))
    return builder.as_markup()
