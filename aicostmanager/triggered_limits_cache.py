from __future__ import annotations

from threading import RLock
from typing import Any, List, Optional


class TriggeredLimitsCache:
    """Thread-safe in-memory cache for decrypted triggered limits."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: Optional[List[dict]] = None

    def get(self) -> Optional[List[dict]]:
        with self._lock:
            return self._data

    def set(self, value: List[dict]) -> None:
        with self._lock:
            self._data = value

    def clear(self) -> None:
        with self._lock:
            self._data = None


triggered_limits_cache = TriggeredLimitsCache()
