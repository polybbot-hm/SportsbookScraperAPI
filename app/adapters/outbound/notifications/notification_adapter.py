"""Adaptador de notificaciones (placeholder para futura iteración)."""
from typing import Any, Dict

from app.domain.ports.outbound.notification_port import NotificationPort


class NotificationAdapter(NotificationPort):
    """Placeholder: no envía notificaciones. Se implementará Telegram/webhooks más adelante."""

    def send(self, channel: str, payload: Dict[str, Any]) -> None:
        pass  # Sin implementación por ahora
