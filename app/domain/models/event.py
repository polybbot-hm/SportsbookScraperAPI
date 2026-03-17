"""Modelo de evento (partido)."""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


@dataclass(frozen=True)
class Event:
    """Partido o evento deportivo."""

    external_id: str
    home_team: str
    away_team: str
    league_name: str
    sport: str
    event_date: Optional[datetime] = None

    @property
    def match_label(self) -> str:
        """Etiqueta legible del partido."""
        return f"{self.home_team} vs {self.away_team}"

    @property
    def normalized_key(self) -> str:
        """Slug canónico independiente del bookmaker: 'villarreal-cf_real-sociedad_20260320'."""
        date_part = self.event_date.strftime("%Y%m%d") if self.event_date else "nodate"
        return f"{_slugify(self.home_team)}_{_slugify(self.away_team)}_{date_part}"
