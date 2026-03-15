"""Tests del caso de uso de scraping."""
from datetime import datetime
from decimal import Decimal

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.services.scraping_use_case import ScrapingUseCase
from tests.mocks.fake_cache import FakeCache
from tests.mocks.fake_repository import FakeOddsRepository
from tests.mocks.fake_scraper import FakeScraper


def _snapshot(partido: str, mercado: str, selection: str, cuota: float):
    home, away = partido.split(" vs ")
    event = Event(external_id="e1", home_team=home, away_team=away, league_name="LaLiga", sport="soccer")
    return OddsSnapshot(
        event=event,
        market_name=mercado,
        market_type=MarketType.FALTAS,
        selection_name=selection,
        odds_value=Decimal(str(cuota)),
        bookmaker=BookmakerName.CODERE,
        scraped_at=datetime(2025, 3, 4, 12, 0),
    )


def test_run_returns_snapshots_and_saves():
    repo = FakeOddsRepository()
    cache = FakeCache()
    snapshots = [_snapshot("A vs B", "Faltas", "Local", 1.85)]
    scrapers = {"codere": FakeScraper(BookmakerName.CODERE, snapshots)}
    use_case = ScrapingUseCase(scrapers=scrapers, repository=repo, cache=cache)

    result = use_case.run(bookmaker="codere", league_name="LaLiga")

    assert len(result) == 1
    assert len(repo.snapshots) == 1
    assert "odds:*" in cache.invalidated_patterns


def test_run_unknown_bookmaker_returns_empty():
    repo = FakeOddsRepository()
    cache = FakeCache()
    use_case = ScrapingUseCase(scrapers={}, repository=repo, cache=cache)

    result = use_case.run(bookmaker="unknown")

    assert result == []
    assert len(repo.snapshots) == 0
