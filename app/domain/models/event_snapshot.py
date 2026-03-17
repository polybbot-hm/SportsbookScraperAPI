"""Modelo agregado de snapshot de cuotas por evento (nuevo modelo principal)."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.models.bookmaker import BookmakerName
from app.domain.models.competition import Competition
from app.domain.models.event import Event
from app.domain.models.market_category import MarketCategorySnapshot


@dataclass
class EventSnapshot:
    """
    Snapshot completo de cuotas para un evento y una casa de apuestas.

    Agrupa todas las categorías de mercado disponibles en la casa para ese partido.
    Este es el modelo principal para MongoDB y los nuevos scrapers.
    """

    bookmaker: BookmakerName
    competition: Competition
    event: Event
    scraped_at: datetime
    market_categories: list[MarketCategorySnapshot] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def total_markets(self) -> int:
        return sum(cat.total_markets for cat in self.market_categories)

    @property
    def available_category_keys(self) -> list[str]:
        return [cat.category_key for cat in self.market_categories if cat.markets]

    def get_category(self, category_key: str) -> MarketCategorySnapshot | None:
        return next(
            (cat for cat in self.market_categories if cat.category_key == category_key),
            None,
        )
