"""In-memory log handler for viewing recent logs from the bot.

Stores the last N formatted log records in a ``collections.deque``
so they can be retrieved on demand without writing to disk.
"""
import logging
from collections import deque
from typing import List

# Singleton deque shared across the module
_LOG_BUFFER: deque[str] = deque(maxlen=200)


class InMemoryLogHandler(logging.Handler):
    """Logging handler that keeps recent records in memory."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            _LOG_BUFFER.append(msg)
        except Exception:
            self.handleError(record)


def get_recent_logs(n: int = 50) -> List[str]:
    """Return the last *n* log lines (oldest first)."""
    items = list(_LOG_BUFFER)
    return items[-n:]
