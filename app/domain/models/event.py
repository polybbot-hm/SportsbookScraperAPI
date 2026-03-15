"""Modelo de evento (partido)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
