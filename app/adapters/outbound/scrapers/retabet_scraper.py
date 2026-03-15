"""Scraper de Retabet (placeholder)."""
from typing import List, Optional

from app.domain.models import OddsSnapshot
from app.domain.ports.outbound.bookmaker_scraper_port import BookmakerScraperPort


class RetabetScraper(BookmakerScraperPort):
    """Placeholder: implementación futura para Retabet."""

    def scrape_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
        target_categories=None,
        exact_league_match: bool = False,
    ) -> List[OddsSnapshot]:
        raise NotImplementedError("Retabet scraper no implementado aún")
