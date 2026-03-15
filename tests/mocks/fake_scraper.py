"""Scraper falso para tests."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.ports.outbound.bookmaker_scraper_port import BookmakerScraperPort


class FakeScraper(BookmakerScraperPort):
    def __init__(self, bookmaker: BookmakerName, results: Optional[List[OddsSnapshot]] = None):
        self.bookmaker = bookmaker
        self.results = results or []

    def scrape_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
        target_categories=None,
        exact_league_match: bool = False,
    ) -> List[OddsSnapshot]:
        return list(self.results)
