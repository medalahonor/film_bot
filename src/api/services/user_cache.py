"""In-memory TTL cache for authenticated users.

Avoids a DB round-trip on every request for recently seen users.
TTL is intentionally short (60 s) so that admin block/unblock
takes effect quickly even without explicit invalidation.
Admin routes call ``invalidate`` explicitly for instant effect.

NOTE: Cache is per-process. With multiple uvicorn workers each process
has its own cache; DB remains the source of truth.
"""
import time
from typing import Optional

from api.database.models import User

_TTL_SECONDS = 60

# {telegram_id: (detached_user_instance, monotonic_timestamp)}
_cache: dict[int, tuple[User, float]] = {}


def get_cached(telegram_id: int) -> Optional[User]:
    """Return cached detached User or None if absent/expired."""
    entry = _cache.get(telegram_id)
    if entry is None:
        return None
    user, ts = entry
    if time.monotonic() - ts > _TTL_SECONDS:
        del _cache[telegram_id]
        return None
    return user


def set_cached(user: User) -> None:
    """Store a detached User instance in the cache."""
    _cache[user.telegram_id] = (user, time.monotonic())


def invalidate(telegram_id: int) -> None:
    """Remove a user from the cache (call after allow/block operations)."""
    _cache.pop(telegram_id, None)
