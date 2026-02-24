"""Main entry point for the bot."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeDefault

from bot.config import config
from bot.middlewares import AccessCheckMiddleware, ErrorLoggingMiddleware
from bot.log_handler import InMemoryLogHandler

# Import handlers
from bot.handlers import session, admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Attach in-memory handler so admins can view recent logs from the bot
_mem_handler = InMemoryLogHandler()
_mem_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
))
logging.getLogger().addHandler(_mem_handler)

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Register bot commands for the Telegram menu button."""
    common_commands = [
        BotCommand(command="start", description="Открыть приложение киноклуба"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(common_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(common_commands, scope=BotCommandScopeDefault())

    private_commands = [
        BotCommand(command="start", description="Открыть приложение"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="admin", description="Панель управления"),
    ]
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

    logger.info("Bot commands registered successfully")


async def main() -> None:
    """Main function to start the bot."""
    try:
        config.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning("Failed to set bot commands: %s", e)

    dp = Dispatcher()

    # Middleware
    dp.message.outer_middleware(ErrorLoggingMiddleware())
    dp.callback_query.outer_middleware(ErrorLoggingMiddleware())
    dp.message.middleware(AccessCheckMiddleware())
    dp.callback_query.middleware(AccessCheckMiddleware())

    # Routers
    dp.include_router(session.router)
    dp.include_router(admin.router)

    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        sys.exit(1)
