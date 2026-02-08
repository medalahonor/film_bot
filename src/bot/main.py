"""Main entry point for the bot."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeDefault

from bot.config import config
from bot.middlewares import (
    AccessCheckMiddleware,
    PollAnswerLoggingMiddleware,
    ErrorLoggingMiddleware,
)
from bot.database import init_db

# Import handlers
from bot.handlers import session, proposals, voting, rating, leaderboard, admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Register bot commands for the Telegram menu button.
    
    Sets different command lists for group chats and private (admin) chats.
    """
    # Minimal slash commands — everything else is in the reply keyboard
    common_commands = [
        BotCommand(command="start", description="Показать клавиатуру"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(common_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(common_commands, scope=BotCommandScopeDefault())

    # Commands for private chats (admin only)
    private_commands = [
        BotCommand(command="admin_help", description="Админская справка"),
        BotCommand(command="add_movie", description="Добавить фильм вручную"),
        BotCommand(command="add_ratings", description="Добавить оценки"),
        BotCommand(command="list_movies", description="Список фильмов"),
        BotCommand(command="db_stats", description="Статистика БД"),
    ]
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

    logger.info("Bot commands registered successfully")


async def main() -> None:
    """Main function to start the bot."""
    # Validate configuration
    try:
        config.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization error: %s", e)
        sys.exit(1)

    # Create bot instance
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Register bot commands for menu button
    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning("Failed to set bot commands: %s", e)

    # Create dispatcher
    dp = Dispatcher()

    # Register middleware
    # Error logging middleware (outermost — catches all unhandled exceptions)
    dp.message.outer_middleware(ErrorLoggingMiddleware())
    dp.callback_query.outer_middleware(ErrorLoggingMiddleware())

    # Access check middleware
    dp.message.middleware(AccessCheckMiddleware())
    dp.callback_query.middleware(AccessCheckMiddleware())

    # PollAnswer logging (no access check — poll answers have no chat context)
    dp.poll_answer.middleware(PollAnswerLoggingMiddleware())

    # Register routers (handlers)
    dp.include_router(session.router)
    dp.include_router(proposals.router)
    dp.include_router(voting.router)
    dp.include_router(rating.router)
    dp.include_router(leaderboard.router)
    dp.include_router(admin.router)

    logger.info("Starting bot...")
    
    # Start polling
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
