"""Telegram WebApp initData HMAC-SHA256 authentication."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException

from api.config import config


_AUTH_MAX_AGE_SECONDS = 86_400  # 24 hours

_DEV_USER: dict = {
    "id": 1,
    "first_name": "Dev",
    "last_name": "User",
    "username": "dev_user",
}


def _compute_secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def _build_data_check_string(fields: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))


def validate_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData.

    Returns parsed user dict on success.
    Raises HTTPException 401 on invalid/expired data.
    In DEV_MODE returns mock user, skipping validation entirely.
    """
    if config.dev_mode:
        return _DEV_USER

    params = dict(parse_qsl(init_data, keep_blank_values=True))

    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > _AUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="initData expired")

    data_check_string = _build_data_check_string(params)
    secret_key = _compute_secret_key(config.telegram_bot_token)
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid hash")

    user_raw = params.get("user", "{}")
    return json.loads(unquote(user_raw))


async def get_init_data_user(
    x_telegram_initdata: str = Header(None, alias="X-Telegram-InitData"),
) -> dict:
    """FastAPI dependency: parse and validate X-Telegram-InitData header."""
    if not x_telegram_initdata:
        if config.dev_mode:
            return _DEV_USER
        raise HTTPException(
            status_code=401, detail="Missing X-Telegram-InitData header",
        )
    return validate_init_data(x_telegram_initdata)
