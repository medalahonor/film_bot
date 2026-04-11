"""Avatar fetching and persistence service.

Handles downloading avatars from Telegram Bot API and storing them in the DB.
Used by the avatar proxy endpoint and get_current_user dependency.
"""
import logging
from datetime import datetime
from typing import Optional

import aiohttp
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import config
from api.database.models import User

logger = logging.getLogger(__name__)


async def fetch_avatar_from_telegram(telegram_id: int) -> Optional[bytes]:
    """Download the smallest profile photo thumbnail from Telegram Bot API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{config.telegram_bot_token}/getUserProfilePhotos",
                params={"user_id": telegram_id, "limit": 1},
            ) as r1:
                payload = await r1.json()

            if not payload.get("ok") or not payload["result"]["photos"]:
                return None

            file_id = payload["result"]["photos"][0][0]["file_id"]

            async with session.get(
                f"https://api.telegram.org/bot{config.telegram_bot_token}/getFile",
                params={"file_id": file_id},
            ) as r2:
                file_payload = await r2.json()

            file_path = file_payload["result"]["file_path"]

            async with session.get(
                f"https://api.telegram.org/file/bot{config.telegram_bot_token}/{file_path}"
            ) as r3:
                return await r3.read()
    except Exception:
        logger.warning("Failed to fetch avatar for user %s", telegram_id)
        return None


async def refresh_avatar_if_needed(db: AsyncSession, user: User) -> None:
    """Fetch avatar from Telegram and save to DB if not yet fetched.

    Called from get_current_user on each webapp open. Only fetches when
    avatar_updated_at is None (first time or never fetched).
    Best-effort: errors are logged but never block authentication.
    """
    if user.avatar_updated_at is not None:
        return

    try:
        avatar_bytes = await fetch_avatar_from_telegram(user.telegram_id)
        now = datetime.utcnow()
        await db.execute(
            update(User)
            .where(User.telegram_id == user.telegram_id)
            .values(avatar=avatar_bytes, avatar_updated_at=now)
        )
        await db.commit()
        user.avatar = avatar_bytes
        user.avatar_updated_at = now
    except Exception:
        logger.warning("Failed to refresh avatar for user %s", user.telegram_id)
