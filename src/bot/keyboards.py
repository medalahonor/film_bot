"""Keyboards for the bot.

All complex UI is now in the WebApp (React + FastAPI).
The bot only needs a single button that opens the WebApp.

ReplyKeyboardMarkup with KeyboardButtonWebApp works in both private and group chats,
unlike InlineKeyboardMarkup + WebAppInfo which is restricted to private chats only.
"""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import config


def get_webapp_keyboard(webapp_url: str = "") -> ReplyKeyboardMarkup:
    """Reply keyboard with a WebApp button — works in private and group chats."""
    url = webapp_url or config.WEBAPP_URL
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎬 Открыть киноклуб", web_app=WebAppInfo(url=url))]],
        resize_keyboard=True,
    )
