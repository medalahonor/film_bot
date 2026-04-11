"""Users API routes."""
from typing import Optional

import aiohttp
from fastapi import APIRouter, Depends, Response

from api.config import config
from api.dependencies import get_current_user
from api.database.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


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

# Simple in-memory cache: {telegram_id: bytes | None}
# None means "no photo"; refreshes on restart.
_avatar_cache: dict[int, Optional[bytes]] = {}


@router.get("/{telegram_id}/avatar")
async def get_user_avatar(telegram_id: int) -> Response:
    """Proxy Telegram profile photo. Public endpoint — used in <img> src."""
    if telegram_id in _avatar_cache:
        data = _avatar_cache[telegram_id]
        if data is None:
            return Response(status_code=404)
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: get file_id of the first profile photo
            async with session.get(
                f"https://api.telegram.org/bot{config.telegram_bot_token}/getUserProfilePhotos",
                params={"user_id": telegram_id, "limit": 1},
            ) as r1:
                payload = await r1.json()

            if not payload.get("ok") or not payload["result"]["photos"]:
                _avatar_cache[telegram_id] = None
                return Response(status_code=404)

            # Use the smallest thumbnail to keep responses fast
            file_id = payload["result"]["photos"][0][0]["file_id"]

            # Step 2: resolve file path
            async with session.get(
                f"https://api.telegram.org/bot{config.telegram_bot_token}/getFile",
                params={"file_id": file_id},
            ) as r2:
                file_payload = await r2.json()

            file_path = file_payload["result"]["file_path"]

            # Step 3: download the photo
            async with session.get(
                f"https://api.telegram.org/file/bot{config.telegram_bot_token}/{file_path}"
            ) as r3:
                photo_bytes = await r3.read()

        _avatar_cache[telegram_id] = photo_bytes
        return Response(
            content=photo_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception:
        _avatar_cache[telegram_id] = None
        return Response(status_code=404)
