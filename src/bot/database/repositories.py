"""Repository functions for database access.

All repeated database queries used by handlers should go through this
module to avoid duplication and keep the handler layer thin.
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import config
from bot.database.models import Group, User, Session
from bot.database.status_manager import get_status_by_code, STATUS_COMPLETED

logger = logging.getLogger(__name__)


def resolve_telegram_group_id(chat_id: int, chat_type: str) -> int:
    """Return the Telegram group ID, mapping private chats to the configured group.

    In private chats (admin), the bot operates on the configured GROUP_ID.
    In group/supergroup chats, the chat_id itself is the group ID.
    """
    if chat_type == "private":
        return config.GROUP_ID
    return chat_id


async def get_group_by_telegram_id(
    db: AsyncSession,
    telegram_id: int,
) -> Optional[Group]:
    """Get a group by its Telegram chat ID."""
    result = await db.execute(
        select(Group).where(Group.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_group(
    db: AsyncSession,
    telegram_id: int,
    name: Optional[str] = None,
) -> Group:
    """Get an existing group or create a new one."""
    group = await get_group_by_telegram_id(db, telegram_id)
    if not group:
        group = Group(telegram_id=telegram_id, name=name)
        db.add(group)
        await db.commit()
        await db.refresh(group)
        logger.info("Created new group: %d", telegram_id)
    return group


async def get_or_create_user(
    db: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> User:
    """Get an existing user or create a new one."""
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created new user: %d", telegram_id)
    return user


async def get_user_by_username(
    db: AsyncSession,
    username: str,
) -> Optional[User]:
    """Get a user by their Telegram username."""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_active_session(
    db: AsyncSession,
    group_id: int,
    status_code: str,
) -> Optional[Session]:
    """Get the most recent session for a group with a specific status.

    Args:
        db: Database session
        group_id: Internal group ID (not Telegram chat ID)
        status_code: Status code to filter by (e.g. STATUS_COLLECTING)

    Returns:
        Session or None if not found or status not initialized
    """
    status = await get_status_by_code(db, status_code)
    if not status:
        return None
    result = await db.execute(
        select(Session)
        .where(Session.group_id == group_id)
        .where(Session.status_id == status.id)
        .order_by(Session.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_active_session_any(
    db: AsyncSession,
    group_id: int,
) -> Optional[Session]:
    """Get any active (non-completed) session for a group.

    Returns the most recent non-completed session, or None.
    """
    completed_status = await get_status_by_code(db, STATUS_COMPLETED)
    if not completed_status:
        return None
    result = await db.execute(
        select(Session)
        .where(Session.group_id == group_id)
        .where(Session.status_id != completed_status.id)
        .order_by(Session.created_at.desc())
    )
    return result.scalar_one_or_none()
