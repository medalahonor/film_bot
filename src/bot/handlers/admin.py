"""Admin handler — /admin redirects to WebApp AdminPage."""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import config
from bot.keyboards import get_webapp_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Send a link to the WebApp admin panel."""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ Доступ только для администраторов.")
        return

    if not config.WEBAPP_URL:
        await message.answer("⚠️ WEBAPP_URL не настроен.")
        return

    admin_url = config.WEBAPP_URL.rstrip('/') + '/#/admin'
    logger.info("Admin %s opened WebApp admin panel", message.from_user.id)
    await message.answer(
        "⚙️ <b>Панель управления</b>\n\n"
        "Откройте приложение и перейдите во вкладку «Управление».",
        reply_markup=get_webapp_keyboard(admin_url),
    )
