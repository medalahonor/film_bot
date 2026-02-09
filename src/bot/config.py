"""Configuration module for the bot."""
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration."""

    # Telegram settings
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_IDS: List[int] = [
        int(id.strip())
        for id in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
        if id.strip()
    ]

    # Multi-group settings (parsed by _parse_groups)
    _raw_groups: str = os.getenv("TELEGRAM_GROUP_IDS", "")
    GROUP_IDS: List[int] = []
    GROUP_TOPIC_MAP: Dict[int, Optional[int]] = {}

    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://filmbot:password@localhost:5432/filmbot"
    )

    @classmethod
    def _parse_groups(cls) -> None:
        """Parse TELEGRAM_GROUP_IDS into GROUP_IDS and GROUP_TOPIC_MAP."""
        cls.GROUP_IDS = []
        cls.GROUP_TOPIC_MAP = {}
        for token in cls._raw_groups.split(","):
            token = token.strip()
            if not token or token == "0":
                continue
            parts = token.split(":", 1)
            group_id = int(parts[0])
            topic_id = int(parts[1]) if len(parts) > 1 and parts[1].strip() else None
            cls.GROUP_IDS.append(group_id)
            cls.GROUP_TOPIC_MAP[group_id] = topic_id

    # Validation
    @classmethod
    def validate(cls) -> None:
        """Validate configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not cls.GROUP_IDS:
            raise ValueError("TELEGRAM_GROUP_IDS is not set or empty")
        if not cls.ADMIN_IDS:
            raise ValueError("TELEGRAM_ADMIN_IDS is not set")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")


Config._parse_groups()
config = Config()
