"""Puerto (interfaz) para scrapers de casas de apuestas."""
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from app.domain.models import Event, OddsSnapshot


class BookmakerScraperPort(ABC):
    """Contrato que debe cumplir cada adaptador de scraping por casa de apuestas."""

    @abstractmethod
    def scrape_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
        target_categories=None,
        exact_league_match: bool = False,
    ) -> List[OddsSnapshot]:
        """
        Scrapea los mercados de las categorías configuradas.
        Si league_name es None, itera todas las ligas disponibles.
        Si target_categories es None, usa las categorías por defecto del scraper.
        """
        ...

    def scrape_fouls_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
    ) -> List[OddsSnapshot]:
        """Wrapper de compatibilidad: delega en scrape_markets."""
        return self.scrape_markets(league_name=league_name, sport_handle=sport_handle)
