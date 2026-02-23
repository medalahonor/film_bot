"""Best-effort Telegram group notifications via raw Bot API (no aiogram)."""
import logging
from typing import Optional

import aiohttp

from api.config import config

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def _send(
    group_telegram_id: int,
    text: str,
    topic_id: Optional[int] = None,
) -> None:
    """Send a message to a Telegram group. Errors are logged and swallowed."""
    url = _TELEGRAM_API.format(token=config.telegram_bot_token)
    payload: dict = {
        "chat_id": group_telegram_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if topic_id:
        payload["message_thread_id"] = topic_id

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(
                        "Telegram notify failed for chat %s: %s %s",
                        group_telegram_id, resp.status, body[:200],
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notify error for chat %s: %s", group_telegram_id, exc)


def _topic_for(group_telegram_id: int) -> Optional[int]:
    """Look up topic_id for a group from config (TELEGRAM_GROUP_IDS env var)."""
    return config.group_topic_map.get(group_telegram_id)


async def notify_movie_proposed(
    group_telegram_id: int,
    movie_title: str,
    movie_type: str,
    slot: int,
    proposer_username: Optional[str],
    proposer_first_name: Optional[str],
) -> None:
    icon = "📺" if movie_type == "serial" else "🎬"
    proposer = f"@{proposer_username}" if proposer_username else (proposer_first_name or "Участник")
    text = f"{icon} <b>{movie_title}</b> предложен в Слот {slot} пользователем {proposer}"
    await _send(group_telegram_id, text, _topic_for(group_telegram_id))


async def notify_voting_finalized(
    group_telegram_id: int,
    winner_titles: dict[int, str],
) -> None:
    lines = ["🏆 <b>Голосование завершено!</b>"]
    for slot in (1, 2):
        title = winner_titles.get(slot, "—")
        lines.append(f"Слот {slot}: <b>{title}</b>")
    await _send(group_telegram_id, "\n".join(lines), _topic_for(group_telegram_id))


async def notify_session_status_changed(
    group_telegram_id: int,
    new_status: str,
) -> None:
    status_labels = {
        "collecting": "🎬 Сбор предложений",
        "voting": "🗳️ Голосование",
        "rating": "⭐ Выставление оценок",
        "completed": "✅ Сессия завершена",
    }
    label = status_labels.get(new_status, new_status)
    text = f"📢 Статус сессии изменён: <b>{label}</b>"
    await _send(group_telegram_id, text, _topic_for(group_telegram_id))
