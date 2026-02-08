"""Shared utility functions for message management in multi-step flows.

Every multi-step (FSM) handler should follow the same cleanup pattern:
1. Delete the user's message on each step.
2. Replace the bot's prompt message instead of sending new ones.
3. At the end of the flow, only the final result message remains.

The bot's current prompt message ID is stored in FSM data as ``bot_message_id``.
The ``↩️ Отмена`` handler in session.py already reads ``bot_message_id``
on cancel, so all flows that use these helpers get proper cancel cleanup
for free.
"""
import logging

from aiogram.types import Message
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


async def try_delete_message(message: Message) -> None:
    """Try to delete a message, silently ignoring errors."""
    try:
        await message.delete()
    except Exception:
        pass


async def replace_bot_message(
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup=None,
) -> None:
    """Replace the bot's prompt message with new content.

    Deletes the previous bot message (tracked via ``bot_message_id``
    in FSM data) and sends a fresh one.  The new message ID is written
    back to FSM so later calls stay consistent.

    Can be called with ``callback.message`` as the *message* parameter
    when handling inline-button callbacks.
    """
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    if bot_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=bot_message_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to delete message %s in chat %s: %s",
                bot_message_id,
                message.chat.id,
                exc,
            )

    new_msg = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(bot_message_id=new_msg.message_id)


async def abort_flow(
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup=None,
) -> None:
    """Abort an FSM flow: clear state, remove bot prompt, send error.

    Use when the flow cannot continue (missing data, validation error, etc.)
    and the user should see a final error/info message.
    """
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")
    await state.clear()

    if bot_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=bot_message_id,
            )
        except Exception:
            pass

    await message.answer(text, reply_markup=reply_markup)


async def finish_flow(message: Message, state: FSMContext) -> None:
    """Finish an FSM flow: delete bot prompt and clear state.

    The caller is responsible for sending the final result message
    **after** calling this helper.
    """
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")
    await state.clear()

    if bot_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=bot_message_id,
            )
        except Exception:
            pass
