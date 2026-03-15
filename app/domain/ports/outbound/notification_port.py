"""Puerto para notificaciones (placeholder para futura iteración)."""
from abc import ABC, abstractmethod
from typing import Any, Dict


class NotificationPort(ABC):
    """Contrato para enviar notificaciones (Telegram, webhooks, etc.)."""

    @abstractmethod
    def send(self, channel: str, payload: Dict[str, Any]) -> None:
        """Envía una notificación. channel y payload se definirán en próxima iteración."""
        ...
