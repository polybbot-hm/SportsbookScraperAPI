"""Modelo de cuota (snapshot)."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.domain.models.bookmaker import BookmakerName
from app.domain.models.event import Event
from app.domain.models.market import MarketType


@dataclass
class OddsSnapshot:
    """Snapshot de una cuota en un momento dado (para histórico)."""

    event: Event
    market_name: str
    market_type: MarketType
    selection_name: str
    odds_value: Decimal
    bookmaker: BookmakerName
    scraped_at: datetime

    # Opcional: id de persistencia (se rellena al guardar en DB)
    id: Optional[str] = None
    event_id: Optional[str] = None
    market_id: Optional[str] = None
