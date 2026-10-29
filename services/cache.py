"""Process-wide TTL cache with retries and stale-on-error fallback.

Every data service returns a DataResult so the UI can always show *when* data was fetched,
whether it is a stale fallback, and why a refresh failed.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable

import config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataResult:
    data: Any
    fetched_at: datetime | None
    source: str = config.SOURCE_NAME
    stale: bool = False
    error: str | None = None
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None or self.stale

    @property
    def has_data(self) -> bool:
        d = self.data
        if d is None:
            return False
        if hasattr(d, "empty"):
            return not d.empty
        if isinstance(d, (list, dict, tuple, set)):
            return len(d) > 0
        return True


@dataclass
class _Entry:
    result: DataResult
    stored_at: float


_store: dict[str, _Entry] = {}
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(key, threading.Lock())


def _describe(exc: Exception) -> str:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {text}"[:300] if text else type(exc).__name__


def fetch(
    key: str,
    ttl: float,
    loader: Callable[[], Any],
    retries: int = 2,
    backoff: float = 0.6,
    sleep: Callable[[float], None] = time.sleep,
) -> DataResult:
    """Return cached data if fresh; otherwise call `loader` with retries.

    On failure, return the last good value flagged `stale=True` (with the error), or an
    error result with `data=None` if nothing was ever cached.
    """
    now = time.monotonic()
    entry = _store.get(key)
    if entry and now - entry.stored_at < ttl and entry.result.error is None:
        return replace(entry.result, cached=True)

    with _lock_for(key):
        entry = _store.get(key)  # another thread may have refreshed meanwhile
        if entry and time.monotonic() - entry.stored_at < ttl and entry.result.error is None:
            return replace(entry.result, cached=True)

        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                data = loader()
                result = DataResult(data=data, fetched_at=datetime.now(timezone.utc))
                _store[key] = _Entry(result, time.monotonic())
                return result
            except Exception as exc:  # yfinance raises many exception types
                last_exc = exc
                log.warning("fetch %s failed (attempt %d): %s", key, attempt + 1, _describe(exc))
                if attempt < retries:
                    sleep(backoff * (2**attempt))

        error = _describe(last_exc) if last_exc else "Unknown error"
        if entry and entry.result.error is None:
            return replace(entry.result, stale=True, error=error, cached=True)
        return DataResult(data=None, fetched_at=None, error=error)


def invalidate(prefix: str = "") -> int:
    """Drop cached entries whose key starts with prefix (all when empty). Returns count."""
    keys = [k for k in list(_store) if k.startswith(prefix)]
    for k in keys:
        _store.pop(k, None)
    return len(keys)
