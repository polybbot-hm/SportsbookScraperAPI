"""Scraper de Paf (placeholder)."""
from typing import List, Optional

from app.domain.models import OddsSnapshot
from app.domain.ports.outbound.bookmaker_scraper_port import BookmakerScraperPort


class PafScraper(BookmakerScraperPort):
    """Placeholder: implementación futura para Paf."""

    def scrape_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
        target_categories=None,
        exact_league_match: bool = False,
    ) -> List[OddsSnapshot]:
        raise NotImplementedError("Paf scraper no implementado aún")
