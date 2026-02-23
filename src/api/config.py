"""API configuration — loaded from environment variables."""
import os
from typing import Optional


def _parse_group_topics(raw: str) -> dict[int, Optional[int]]:
    """Parse TELEGRAM_GROUP_IDS into {group_id: topic_id_or_None}."""
    result: dict[int, Optional[int]] = {}
    for token in raw.split(","):
        token = token.strip()
        if not token or token == "0":
            continue
        parts = token.split(":", 1)
        group_id = int(parts[0])
        topic_id = int(parts[1]) if len(parts) > 1 and parts[1].strip() else None
        result[group_id] = topic_id
    return result


class Config:
    telegram_bot_token: str = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_admin_ids: list[int] = [
        int(x) for x in os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip()
    ]
    database_url: str = os.environ["DATABASE_URL"]
    webapp_origin: str = os.environ.get("WEBAPP_ORIGIN", "")
    webapp_url: str = os.environ.get("WEBAPP_URL", "")
    group_topic_map: dict[int, Optional[int]] = _parse_group_topics(
        os.environ.get("TELEGRAM_GROUP_IDS", "")
    )


config = Config()
