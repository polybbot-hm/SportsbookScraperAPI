"""Caché en memoria con TTL (cachetools)."""
import re
from typing import Any, Optional

from cachetools import TTLCache

from app.domain.ports.outbound.cache_port import CachePort


class InMemoryCache(CachePort):
    """Implementación de CachePort con TTLCache."""

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 300):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if ttl_seconds is not None:
            # TTLCache global: no podemos TTL por clave; guardamos con el TTL por defecto
            self._cache[key] = value
        else:
            self._cache[key] = value

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> None:
        # Convierte patrón tipo "odds:*" en regex
        regex = pattern.replace("*", ".*")
        to_remove = [k for k in list(self._cache.keys()) if re.match(regex, k)]
        for k in to_remove:
            self._cache.pop(k, None)
