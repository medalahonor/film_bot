"""Keyboards for the bot.

All complex UI is now in the WebApp (React + FastAPI).
The bot only needs a single inline button that opens the WebApp.

WebApp buttons (both inline and reply) are restricted to private chats by Telegram API.
In group chats, /start sends a text link directing users to the private chat.
"""
from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import config


def get_webapp_keyboard(webapp_url: str = "") -> InlineKeyboardMarkup:
    """Inline WebApp button — private chats only."""
    url = webapp_url or config.WEBAPP_URL
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Открыть киноклуб", web_app=WebAppInfo(url=url))
    return builder.as_markup()


def get_group_open_keyboard() -> InlineKeyboardMarkup:
    """Inline URL button for group chats pointing to BOT_URL.

    BOT_URL can be set to https://t.me/{username} (opens private chat)
    or https://t.me/{username}/{app_name} (opens Mini App directly, requires BotFather registration).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Открыть киноклуб", url=config.BOT_URL)
    return builder.as_markup()
