"""FastAPI shared dependencies."""
from typing import AsyncGenerator

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from api.auth import get_init_data_user
from api.config import config
from api.database.models import User

_engine = create_async_engine(config.database_url, pool_pre_ping=True)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


async def get_current_user(
    tg_user: dict = Depends(get_init_data_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve Telegram user → DB User. Creates with is_allowed=False if new.
    Users in TELEGRAM_ADMIN_IDS are auto-allowed.
    """
    from sqlalchemy import select

    telegram_id = int(tg_user["id"])
    is_telegram_admin = telegram_id in config.telegram_admin_ids

    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
            is_allowed=is_telegram_admin,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif is_telegram_admin and not user.is_allowed:
        user.is_allowed = True
        await db.commit()

    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    return user


async def get_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin (by Telegram ID)."""
    if user.telegram_id not in config.telegram_admin_ids:
        raise HTTPException(status_code=403, detail="Admin only")
    return user
