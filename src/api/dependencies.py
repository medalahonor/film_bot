"""FastAPI shared dependencies."""
from typing import AsyncGenerator

from fastapi import Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from api.auth import get_init_data_user
from api.config import config
from api.database.models import User
from api.services.avatar_service import refresh_avatar_if_needed
from api.services.user_cache import get_cached, invalidate, set_cached

_engine = create_async_engine(config.database_url, pool_pre_ping=True)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


def _profile_changed(user: User, tg_user: dict) -> bool:
    return (
        user.username != tg_user.get("username")
        or user.first_name != tg_user.get("first_name")
        or user.last_name != tg_user.get("last_name")
    )


async def _update_profile(db: AsyncSession, user: User, tg_user: dict) -> None:
    user.username = tg_user.get("username")
    user.first_name = tg_user.get("first_name")
    user.last_name = tg_user.get("last_name")
    await db.execute(
        update(User)
        .where(User.telegram_id == user.telegram_id)
        .values(
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
    )
    await db.commit()


async def get_current_user(
    tg_user: dict = Depends(get_init_data_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve Telegram user → DB User.

    On every request:
    - Checks in-memory TTL cache first (avoids DB round-trip).
    - If profile data changed (name/username) — updates DB and cache.
    - Creates new user with is_allowed=False if not found.
    - Auto-allows users listed in TELEGRAM_ADMIN_IDS.
    """
    telegram_id = int(tg_user["id"])
    should_auto_allow = telegram_id in config.telegram_admin_ids or config.dev_mode

    cached = get_cached(telegram_id)
    if cached is not None:
        if _profile_changed(cached, tg_user):
            await _update_profile(db, cached, tg_user)
            set_cached(cached)
        if should_auto_allow and not cached.is_allowed:
            cached.is_allowed = True
            await db.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(is_allowed=True)
            )
            await db.commit()
            set_cached(cached)
        if not cached.is_allowed:
            raise HTTPException(status_code=403, detail="Access denied")
        await refresh_avatar_if_needed(db, cached)
        return cached

    # Cache miss — full DB lookup
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
            is_allowed=should_auto_allow,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        changed = _profile_changed(user, tg_user)
        if changed:
            await _update_profile(db, user, tg_user)
        if should_auto_allow and not user.is_allowed:
            user.is_allowed = True
            await db.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(is_allowed=True)
            )
            await db.commit()

    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    await refresh_avatar_if_needed(db, user)
    db.expunge(user)
    set_cached(user)
    return user


async def get_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin (by Telegram ID)."""
    if user.telegram_id not in config.telegram_admin_ids:
        raise HTTPException(status_code=403, detail="Admin only")
    return user
