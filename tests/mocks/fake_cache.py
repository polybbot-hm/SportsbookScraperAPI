"""Caché falso para tests."""
from typing import Any, Optional

from app.domain.ports.outbound.cache_port import CachePort


class FakeCache(CachePort):
    def __init__(self):
        self._store: dict = {}
        self.invalidated = []
        self.invalidated_patterns = []

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        self._store[key] = value

    def invalidate(self, key: str) -> None:
        self.invalidated.append(key)
        self._store.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> None:
        self.invalidated_patterns.append(pattern)
        to_remove = [k for k in self._store if pattern.replace("*", "") in k or (pattern == "odds:*" and k.startswith("odds:"))]
        for k in to_remove:
            del self._store[k]
