"""Configuration module for the bot."""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration."""
    
    # Telegram settings
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    GROUP_ID: int = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
    ADMIN_IDS: List[int] = [
        int(id.strip()) 
        for id in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") 
        if id.strip()
    ]
    TOPIC_IDS: List[int] = [
        int(id.strip())
        for id in os.getenv("TELEGRAM_TOPIC_IDS", "").split(",")
        if id.strip()
    ]
    
    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://filmbot:password@localhost:5432/filmbot"
    )
    
    # Validation
    @classmethod
    def validate(cls) -> None:
        """Validate configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if cls.GROUP_ID == 0:
            raise ValueError("TELEGRAM_GROUP_ID is not set")
        if not cls.ADMIN_IDS:
            raise ValueError("TELEGRAM_ADMIN_IDS is not set")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")


config = Config()
