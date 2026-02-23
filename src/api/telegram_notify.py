"""Best-effort Telegram group notifications via raw Bot API (no aiogram)."""
import logging

import aiohttp

from api.config import config

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def _send(
    group_telegram_id: int,
    text: str,
    topic_id: int | None = None,
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


async def _notify_all(text: str) -> None:
    """Send a message to all configured Telegram groups."""
    for group_id, topic_id in config.group_topic_map.items():
        await _send(group_id, text, topic_id)


async def notify_movie_proposed(
    movie_title: str,
    movie_type: str,
    slot: int,
    proposer_username: str | None,
    proposer_first_name: str | None,
) -> None:
    icon = "📺" if movie_type == "serial" else "🎬"
    proposer = f"@{proposer_username}" if proposer_username else (proposer_first_name or "Участник")
    text = f"{icon} <b>{movie_title}</b> предложен в Слот {slot} пользователем {proposer}"
    await _notify_all(text)


async def notify_voting_finalized(
    winner_titles: dict[int, str],
) -> None:
    lines = ["🏆 <b>Голосование завершено!</b>"]
    for slot in (1, 2):
        title = winner_titles.get(slot, "—")
        lines.append(f"Слот {slot}: <b>{title}</b>")
    await _notify_all("\n".join(lines))


async def notify_session_status_changed(
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
    await _notify_all(text)
