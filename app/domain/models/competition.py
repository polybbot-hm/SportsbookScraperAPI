"""Modelo de competición deportiva."""
import re
from dataclasses import dataclass

from app.domain.models.bookmaker import BookmakerName


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


@dataclass(frozen=True)
class Competition:
    """Competición o liga deportiva tal como la identifica cada casa de apuestas."""

    external_id: str
    bookmaker: BookmakerName
    name: str
    sport: str
    normalized_key: str  # slug canónico independiente del bookmaker: "la_liga", "premier_league"

    @property
    def display_name(self) -> str:
        return self.name

    @classmethod
    def build_normalized_key(cls, name: str) -> str:
        """Genera un slug normalizado a partir del nombre de la competición."""
        return _slugify(name).replace("-", "_")
