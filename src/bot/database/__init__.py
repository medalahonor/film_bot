"""Database package."""
from bot.database.session import get_session, init_db
from bot.database.models import (
    Base, User, Group, Admin, Session, SessionStatus, Movie, Vote, Rating
)
from bot.database.status_manager import (
    get_status_by_code,
    init_statuses,
    STATUS_COLLECTING,
    STATUS_VOTING,
    STATUS_RATING,
    STATUS_COMPLETED,
)
from bot.database.repositories import (
    get_group_by_telegram_id,
    get_or_create_group,
    get_or_create_user,
    get_user_by_username,
    get_active_session,
    get_active_session_any,
    resolve_telegram_group_id,
)

__all__ = [
    "get_session", "init_db",
    "Base", "User", "Group", "Admin", "Session", "SessionStatus",
    "Movie", "Vote", "Rating",
    "get_status_by_code", "init_statuses",
    "STATUS_COLLECTING", "STATUS_VOTING", "STATUS_RATING", "STATUS_COMPLETED",
    "get_group_by_telegram_id", "get_or_create_group",
    "get_or_create_user", "get_user_by_username",
    "get_active_session", "get_active_session_any",
    "resolve_telegram_group_id",
]
