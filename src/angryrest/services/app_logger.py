from __future__ import annotations

import logging
from collections import deque

_APP_LOGGER_NAME = "angryrest"
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


class AppLogHandler(logging.Handler):
    """Thread-safe in-memory handler with a 2 MB rolling size cap.

    Oldest records are dropped once the total formatted-message size exceeds
    ``_MAX_BYTES``.  ``emit`` is called from whatever thread triggered the log
    call; Python's GIL makes deque operations atomic for the simple
    append/popleft pattern used here.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self._records: deque[logging.LogRecord] = deque()
        self._total_bytes: int = 0

    def emit(self, record: logging.LogRecord) -> None:
        size = len(record.getMessage().encode("utf-8", errors="replace"))
        self._records.append(record)
        self._total_bytes += size
        # Evict oldest records until we're back under the limit
        while self._total_bytes > _MAX_BYTES and self._records:
            old = self._records.popleft()
            self._total_bytes -= len(old.getMessage().encode("utf-8", errors="replace"))

    def get_records(self) -> list[logging.LogRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()
        self._total_bytes = 0

    def error_count(self) -> int:
        return sum(1 for r in self._records if r.levelno >= logging.ERROR)

    def total_count(self) -> int:
        return len(self._records)


# --- Module-level singleton ---

_handler = AppLogHandler()

_app_logger = logging.getLogger(_APP_LOGGER_NAME)
_app_logger.setLevel(logging.DEBUG)
_app_logger.addHandler(_handler)
_app_logger.propagate = False  # don't leak into the root logger


# --- Public API ---

def get_logger(name: str = "") -> logging.Logger:
    """Return a child logger under the ``angryrest`` namespace.

    Any records emitted by the returned logger (or its children) will be
    captured by the in-memory handler and shown in the Logs panel.
    """
    if name:
        return logging.getLogger(f"{_APP_LOGGER_NAME}.{name}")
    return _app_logger


def get_records() -> list[logging.LogRecord]:
    return _handler.get_records()


def clear_records() -> None:
    _handler.clear()


def error_count() -> int:
    return _handler.error_count()


def total_count() -> int:
    return _handler.total_count()
