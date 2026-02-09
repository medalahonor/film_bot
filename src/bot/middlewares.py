"""Middleware for access control and logging."""
import logging
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, PollAnswer

from bot.config import config

logger = logging.getLogger(__name__)


class AccessCheckMiddleware(BaseMiddleware):
    """Middleware to check if user/chat is authorized to use the bot."""

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Check access and call handler if authorized."""
        # Get chat info based on event type
        if isinstance(event, Message):
            chat = event.chat
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            chat = event.message.chat if event.message else None
            user_id = event.from_user.id
        else:
            # Unknown event type, deny
            return None

        if not chat or not user_id:
            return None

        chat_type = chat.type
        thread_id = _extractThreadId(event)
        event_type = type(event).__name__

        # Log every incoming interaction
        logger.info(
            "event=%s user_id=%d chat_id=%d chat_type=%s topic_id=%s",
            event_type,
            user_id,
            chat.id,
            chat_type,
            thread_id,
        )

        # Check for group/supergroup chats
        if chat_type in ['group', 'supergroup']:
            if chat.id not in config.GROUP_IDS:
                logger.warning(
                    "Rejected: unauthorized group chat_id=%d user_id=%d",
                    chat.id,
                    user_id,
                )
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Бот работает только в авторизованной группе."
                    )
                return None

            # Check topic restriction for supergroups
            if not self._isAllowedTopic(event, chat_type, chat.id):
                logger.info(
                    "Rejected: topic not allowed user_id=%d topic_id=%s",
                    user_id,
                    thread_id,
                )
                return None

            # Authorized group - proceed
            return await handler(event, data)
        
        # Check for private chats (only admins allowed)
        elif chat_type == 'private':
            if user_id not in config.ADMIN_IDS:
                logger.warning(
                    "Rejected: non-admin private chat user_id=%d",
                    user_id,
                )
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Личные сообщения доступны только администраторам."
                    )
                return None
            # Authorized admin - proceed
            data['is_admin'] = True
            return await handler(event, data)
        
        # Unknown chat type
        logger.warning(
            "Rejected: unknown chat_type=%s chat_id=%d user_id=%d",
            chat_type,
            chat.id,
            user_id,
        )
        return None

    @staticmethod
    def _isAllowedTopic(
        event: Message | CallbackQuery,
        chat_type: str,
        chat_id: int,
    ) -> bool:
        """Check if the event comes from an allowed topic.

        Rules:
        - No topic configured for this group → no restriction.
        - Chat is a regular group (not supergroup) → no restriction.
        - Supergroup without forum topics → no restriction.
        - Supergroup with forum topics → allow only configured topic ID.
        """
        topic_id = config.GROUP_TOPIC_MAP.get(chat_id)
        if topic_id is None:
            return True

        if chat_type != "supergroup":
            return True

        thread_id = _extractThreadId(event)
        if thread_id is None:
            return True

        is_allowed = thread_id == topic_id
        if not is_allowed:
            logger.debug(
                "Blocked event in topic %d (allowed: %s for group %d)",
                thread_id,
                topic_id,
                chat_id,
            )
        return is_allowed


class PollAnswerLoggingMiddleware(BaseMiddleware):
    """Middleware to log PollAnswer events.

    PollAnswer events don't have a chat context, so
    AccessCheckMiddleware can't handle them.  This middleware
    ensures every poll answer is recorded in the log.
    """

    async def __call__(
        self,
        handler: Callable[[PollAnswer, Dict[str, Any]], Awaitable[Any]],
        event: PollAnswer,
        data: Dict[str, Any],
    ) -> Any:
        user = event.user
        logger.info(
            "event=PollAnswer user_id=%d poll_id=%s options=%s",
            user.id if user else 0,
            event.poll_id,
            event.option_ids,
        )
        try:
            return await handler(event, data)
        except Exception as exc:
            logger.exception(
                "Error handling PollAnswer from user %d: %s",
                user.id if user else 0, exc,
            )
            raise


class ErrorLoggingMiddleware(BaseMiddleware):
    """Middleware to catch and log unhandled exceptions in handlers.

    Wraps Message and CallbackQuery handlers so that any exception
    that slips through is logged with full traceback.  The exception
    is re-raised so that aiogram's default behaviour is preserved.
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            user_id = event.from_user.id if event.from_user else 0
            event_type = type(event).__name__
            logger.exception(
                "Unhandled error in %s handler for user %d: %s",
                event_type, user_id, exc,
            )
            raise


def _extractThreadId(event: Message | CallbackQuery) -> Optional[int]:
    """Extract message_thread_id from a Message or CallbackQuery."""
    if isinstance(event, Message):
        return event.message_thread_id
    if isinstance(event, CallbackQuery) and event.message:
        return event.message.message_thread_id  # type: ignore[union-attr]
    return None
