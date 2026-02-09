"""Session management handlers."""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.models import Session
from bot.database.session import AsyncSessionLocal
from bot.database.status_manager import (
    get_status_by_code,
    STATUS_COLLECTING,
    STATUS_COMPLETED,
)
from bot.database.repositories import (
    get_or_create_user,
    get_or_create_group,
    get_group_by_telegram_id,
    get_active_session_any,
)
from bot.keyboards import (
    BTN_NEW_SESSION, BTN_STATUS, BTN_CANCEL_SESSION,
    BTN_HELP, BTN_CANCEL, BTN_RATE,
    get_main_menu_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Show welcome message and main menu keyboard."""
    logger.info(
        "User %s called /start in chat %s",
        message.from_user.id, message.chat.id,
    )
    await message.answer(
        "🎬 <b>Добро пожаловать в Киноклуб!</b>\n\n"
        "Используйте кнопки меню внизу экрана для управления ботом.\n"
        "Нажмите <b>❓ Помощь</b> для подробного описания.",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(F.text == BTN_CANCEL)
async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Cancel current FSM operation and return to main menu.

    Also cleans up any stored bot prompt message (e.g. from the
    proposal flow) and deletes the user's cancel message to keep
    the chat tidy.
    """
    current_state = await state.get_state()
    logger.info(
        "User %s cancelled action (state=%s)",
        message.from_user.id, current_state,
    )

    data = await state.get_data()
    bot_message_id = data.get('bot_message_id')
    await state.clear()

    # Delete user's cancel message
    try:
        await message.delete()
    except Exception as exc:
        logger.debug("Failed to delete cancel message: %s", exc)

    # Delete bot's prompt message if it was saved in FSM
    if bot_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=bot_message_id,
            )
        except Exception as exc:
            logger.debug("Failed to delete bot prompt message %s: %s", bot_message_id, exc)

    await message.answer(
        "↩️ Действие отменено.",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(F.text == BTN_NEW_SESSION)
async def create_new_session(message: Message, state: FSMContext) -> None:
    """Create a new film club session via reply keyboard button."""
    await state.clear()
    async with AsyncSessionLocal() as db:
        try:
            from_user = message.from_user
            user = await get_or_create_user(
                db, from_user.id, from_user.username,
                from_user.first_name, from_user.last_name,
            )
            group = await get_or_create_group(
                db, message.chat.id, message.chat.title,
            )

            active_session = await get_active_session_any(db, group.id)
            
            if active_session:
                await message.answer(
                    f"⚠️ Уже есть активная сессия!\n\n"
                    f"Статус: <b>{active_session.status}</b>\n"
                    f"Создана: {active_session.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Нажмите «{BTN_STATUS}» для просмотра деталей."
                )
                return
            
            # Get collecting status
            collecting_status = await get_status_by_code(db, STATUS_COLLECTING)
            if not collecting_status:
                await message.answer("❌ Ошибка: статусы не инициализированы.")
                return
            
            # Create new session
            new_session = Session(
                group_id=group.id,
                created_by=user.id,
                status_id=collecting_status.id,
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            
            # Send and pin message for collecting proposals
            pin_message = await message.answer(
                "🎬 <b>СБОР ПРЕДЛОЖЕНИЙ ОТКРЫТ!</b>\n\n"
                "Чтобы предложить фильм, нажмите кнопку\n"
                "📝 <b>Предложить фильм</b> в меню бота.\n\n"
                "─────────────────\n"
                "✅ <b>Уже предложили (0):</b>\n"
                "(пусто)"
            )
            
            # Pin the message
            try:
                await pin_message.pin(disable_notification=True)
            except Exception as e:
                logger.warning("Failed to pin message: %s", e)
            
            # Update session with pinned message ID
            new_session.pinned_message_id = pin_message.message_id
            await db.commit()
            
            logger.info(
                "User %s created new session %s in group %s",
                message.from_user.id, new_session.id, group.id,
            )
            
        except Exception as e:
            logger.exception("Error creating session: %s", e)
            await message.answer(
                "❌ Произошла ошибка при создании сессии. Попробуйте позже."
            )


@router.message(F.text == BTN_STATUS)
async def show_session_status(message: Message, state: FSMContext) -> None:
    """Show current session status via reply keyboard button."""
    await state.clear()
    logger.info("User %s requested session status", message.from_user.id)
    async with AsyncSessionLocal() as db:
        try:
            group = await get_group_by_telegram_id(db, message.chat.id)

            if not group:
                await message.answer(
                    f"ℹ️ Группа не зарегистрирована. Нажмите «{BTN_NEW_SESSION}» для создания первой сессии."
                )
                return

            session = await get_active_session_any(db, group.id)

            if not session:
                await message.answer(
                    "ℹ️ Нет активной сессии.\n\n"
                    f"Нажмите «{BTN_NEW_SESSION}» для создания новой."
                )
                return
            
            # Format status message
            status_emoji = {
                'collecting': '📝',
                'voting': '🗳',
                'rating': '⭐',
            }.get(session.status, 'ℹ️')
            
            status_text = session.status_obj.name if session.status_obj else session.status
            
            response = (
                f"{status_emoji} <b>Статус текущей сессии</b>\n\n"
                f"Состояние: <b>{status_text}</b>\n"
                f"Создана: {session.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            
            if session.status == 'collecting':
                response += "\n💡 Нажмите 📝 Предложить фильм в меню бота"
            elif session.status == 'voting':
                response += "\n💡 Проголосуйте за фильмы в опросах выше"
            elif session.status == 'rating':
                response += f"\n💡 Нажмите «{BTN_RATE}» для оценки просмотренных фильмов"
            
            await message.answer(response)
            
        except Exception as e:
            logger.exception("Error showing status: %s", e)
            await message.answer(
                "❌ Произошла ошибка при получении статуса."
            )


@router.message(F.text == BTN_CANCEL_SESSION)
async def cancel_session(message: Message, state: FSMContext) -> None:
    """Cancel current session via reply keyboard button."""
    await state.clear()
    async with AsyncSessionLocal() as db:
        try:
            group = await get_group_by_telegram_id(db, message.chat.id)

            if not group:
                await message.answer("ℹ️ Группа не найдена.")
                return

            session = await get_active_session_any(db, group.id)

            if not session:
                await message.answer("ℹ️ Нет активной сессии.")
                return

            # Mark as completed
            completed_status = await get_status_by_code(db, STATUS_COMPLETED)
            if not completed_status:
                await message.answer("❌ Ошибка: статусы не инициализированы.")
                return

            session.status_id = completed_status.id
            session.completed_at = datetime.utcnow()
            await db.commit()
            
            await message.answer(
                "✅ Сессия отменена и помечена как завершенная."
            )
            
            logger.info(
                "Session %s cancelled by user %s",
                session.id, message.from_user.id,
            )
            
        except Exception as e:
            logger.exception("Error cancelling session: %s", e)
            await message.answer(
                "❌ Произошла ошибка при отмене сессии."
            )


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def show_help(message: Message, state: FSMContext) -> None:
    """Show help message with available commands."""
    await state.clear()
    logger.info("User %s requested help", message.from_user.id)
    help_text = (
        "🎬 <b>Бот киноклуба</b>\n\n"
        "Используйте кнопки меню внизу экрана.\n"
        "Если клавиатура пропала — нажмите /start\n\n"

        "<b>📋 Управление сессией:</b>\n"
        "🎬 Новая сессия — создать новую сессию\n"
        "📋 Статус — текущее состояние\n"
        "❌ Отменить сессию — отменить текущую\n\n"

        "<b>🗳 Голосование:</b>\n"
        "🗳 Начать голосование — запустить опросы\n"
        "🏁 Завершить голосование — подвести итоги\n"
        "🔄 Переголосование — при ничьей\n\n"

        "<b>⭐ Рейтинги:</b>\n"
        "⭐ Оценить фильмы — выставить оценку (1-10)\n"
        "✅ Завершить сессию — завершить и показать статистику\n\n"

        "<b>📊 Информация:</b>\n"
        "🏆 Лидерборд — таблица лучших фильмов\n"
        "🔍 Поиск — найти фильм по названию\n"
        "📊 Статистика — общая статистика клуба\n\n"

        "<b>📝 Предложение фильмов:</b>\n"
        "📝 Предложить фильм — выбрать слот и отправить ссылку"
    )

    if message.from_user.id in config.ADMIN_IDS:
        help_text += (
            "\n\n👑 <b>Админские команды (в личке):</b>\n"
            "/admin_help — админская справка"
        )

    await message.answer(help_text, reply_markup=get_main_menu_keyboard())
