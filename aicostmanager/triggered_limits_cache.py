from __future__ import annotations

from threading import RLock
from typing import List, Optional


class TriggeredLimitsCache:
    """Thread-safe in-memory cache for triggered limits payloads."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: Optional[List[dict]] = None
        self._raw: Optional[dict] = None
        self._user: Optional[str] = None

    def get(self) -> Optional[List[dict]]:
        with self._lock:
            return self._data

    def get_raw(self) -> Optional[dict]:
        with self._lock:
            return self._raw

    def get_user(self) -> Optional[str]:
        """Return the user associated with the cached triggered limits."""
        with self._lock:
            return self._user

    def set(
        self, value: List[dict], raw: Optional[dict] = None, user: Optional[str] = None
    ) -> None:
        with self._lock:
            self._data = value
            if raw is not None:
                self._raw = raw
            self._user = user

    def clear(self) -> None:
        with self._lock:
            self._data = None
            self._raw = None
            self._user = None


triggered_limits_cache = TriggeredLimitsCache()
