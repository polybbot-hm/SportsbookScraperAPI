"""Puerto para caché."""
from abc import ABC, abstractmethod
from typing import Any, Optional


class CachePort(ABC):
    """Contrato para caché (get/set/invalidate)."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor por clave. None si no existe o expiró."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Guarda valor con TTL opcional."""
        ...

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """Elimina una clave."""
        ...

    @abstractmethod
    def invalidate_pattern(self, pattern: str) -> None:
        """Elimina todas las claves que coincidan con el patrón (ej: 'odds:*')."""
        ...
