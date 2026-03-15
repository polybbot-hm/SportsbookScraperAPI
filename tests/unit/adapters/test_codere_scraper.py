"""Tests del scraper Codere (con mocks HTTP)."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.outbound.scrapers.codere_scraper import CodereScraper
from app.domain.models import BookmakerName, MarketType


@patch("app.adapters.outbound.scrapers.codere_scraper.get_with_retry")
def test_codere_scraper_returns_empty_when_no_sport(mock_get):
    mock_get.return_value.json.return_value = []
    mock_get.return_value.raise_for_status = MagicMock()
    scraper = CodereScraper()
    result = scraper.scrape_fouls_markets(league_name="LaLiga")
    assert result == []


@patch("app.adapters.outbound.scrapers.codere_scraper.get_with_retry")
def test_codere_scraper_parses_response_into_snapshots(mock_get):
    call_count = [0]

    def make_resp(data):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json = MagicMock(return_value=data)
        return r

    responses = [
        [{"SportHandle": "soccer", "NodeId": 1}],
        [{"Leagues": [{"NodeId": 100, "Name": "LaLiga"}]}],
        {"100": [{"NodeId": 500, "Participants": [
            {"LocalizedNames": {"LocalizedValues": [{"Value": "Real Madrid"}]}},
            {"LocalizedNames": {"LocalizedValues": [{"Value": "Barcelona"}]}},
        ]}]},
        {"CategoriesInformation": [{"CategoryName": "ESTADÍSTICAS", "CategoryId": 10}]},
        [{"Name": "Faltas - Más", "Results": [{"Name": "Local", "Odd": 1.85}, {"Name": "Visitante", "Odd": 2.0}]}],
    ]

    def side_effect_get(url, **kwargs):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return make_resp(responses[idx])

    mock_get.side_effect = side_effect_get
    scraper = CodereScraper()
    result = scraper.scrape_fouls_markets(league_name="LaLiga")

    assert len(result) == 2
    assert result[0].event.match_label == "Real Madrid vs Barcelona"
    assert result[0].market_name == "Faltas - Más"
    assert result[0].bookmaker == BookmakerName.CODERE
    assert result[0].market_type == MarketType.FALTAS
    assert result[0].odds_value == Decimal("1.85")
    assert result[0].selection_name == "Local"
