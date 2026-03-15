"""Tests de que los puertos (interfaces) existen y tienen la firma esperada."""
import inspect

import pytest

from app.domain.ports.outbound import (
    BookmakerScraperPort,
    CachePort,
    NotificationPort,
    OddsRepositoryPort,
)
from app.domain.ports.outbound.bookmaker_scraper_port import BookmakerScraperPort as BSP
from app.domain.ports.outbound.cache_port import CachePort as CP
from app.domain.ports.outbound.odds_repository_port import OddsRepositoryPort as ORP


def test_bookmaker_scraper_port_is_abstract():
    assert getattr(BSP, "scrape_fouls_markets") is not None
    with pytest.raises(TypeError):
        BSP()  # No se puede instanciar sin implementar


def test_odds_repository_port_has_required_methods():
    methods = {"save_snapshots", "get_latest_odds", "get_odds_history", "list_events", "list_leagues_with_market", "upsert_league_has_market"}
    for m in methods:
        assert hasattr(ORP, m), f"Falta método {m}"


def test_cache_port_has_get_set_invalidate():
    assert hasattr(CP, "get") and hasattr(CP, "set") and hasattr(CP, "invalidate")
    assert hasattr(CP, "invalidate_pattern")
