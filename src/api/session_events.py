"""In-memory pub/sub for SSE session change notifications.

NOTE: Works only with a single uvicorn worker (--workers 1).
With multiple workers, subscribers in different processes won't receive
events. For multi-worker setup, replace with Redis pub/sub.
"""
import asyncio
from typing import Set

_subscribers: Set[asyncio.Queue] = set()


def subscribe(queue: asyncio.Queue) -> None:
    _subscribers.add(queue)


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


async def notify_session_changed(data: dict) -> None:
    for queue in list(_subscribers):
        await queue.put(data)
