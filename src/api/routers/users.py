"""Users API routes."""
import time
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import config
from api.dependencies import get_current_user, get_db
from api.database.models import User
from api.services.avatar_service import fetch_avatar_from_telegram

router = APIRouter(prefix="/api/users", tags=["users"])

_AVATAR_CACHE_TTL = 600  # 10 minutes

# {telegram_id: (bytes | None, monotonic_timestamp)}
_avatar_cache: dict[int, tuple[Optional[bytes], float]] = {}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    """Return current user's profile including admin status."""
    return {
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "is_admin": user.telegram_id in config.telegram_admin_ids,
        "is_allowed": user.is_allowed,
    }


def _get_cached_avatar(telegram_id: int) -> tuple[bool, Optional[bytes]]:
    """Check in-memory TTL cache. Returns (hit, data)."""
    entry = _avatar_cache.get(telegram_id)
    if entry is None:
        return False, None
    data, ts = entry
    if time.monotonic() - ts > _AVATAR_CACHE_TTL:
        del _avatar_cache[telegram_id]
        return False, None
    return True, data


def _set_cached_avatar(telegram_id: int, data: Optional[bytes]) -> None:
    _avatar_cache[telegram_id] = (data, time.monotonic())


def _build_avatar_response(data: Optional[bytes]) -> Response:
    if data is None:
        return Response(status_code=404)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def _get_db_avatar(
    db: AsyncSession, telegram_id: int,
) -> tuple[bool, Optional[bytes]]:
    """Read avatar bytes from DB. Returns (found_user, avatar_bytes)."""
    result = await db.execute(
        select(User.avatar).where(User.telegram_id == telegram_id)
    )
    row = result.one_or_none()
    if row is None:
        return False, None
    return True, row[0]


async def _fetch_and_store_avatar(
    db: AsyncSession, telegram_id: int,
) -> Optional[bytes]:
    """Fetch avatar from Telegram API, store in DB, return bytes."""
    from datetime import datetime

    avatar_bytes = await fetch_avatar_from_telegram(telegram_id)
    now = datetime.utcnow()
    await db.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(avatar=avatar_bytes, avatar_updated_at=now)
    )
    await db.commit()
    return avatar_bytes


@router.get("/{telegram_id}/avatar")
async def get_user_avatar(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Proxy Telegram profile photo. Public endpoint — used in <img> src."""
    # Layer 1: in-memory cache
    hit, data = _get_cached_avatar(telegram_id)
    if hit:
        return _build_avatar_response(data)

    # Layer 2: DB
    found, data = await _get_db_avatar(db, telegram_id)
    if found and data is not None:
        _set_cached_avatar(telegram_id, data)
        return _build_avatar_response(data)

    # Layer 3: Telegram API → store in DB
    try:
        data = await _fetch_and_store_avatar(db, telegram_id)
    except Exception:
        data = None

    _set_cached_avatar(telegram_id, data)
    return _build_avatar_response(data)
