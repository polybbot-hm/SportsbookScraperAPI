"""Tests unitarios de modelos de dominio."""
from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.models.bookmaker import BookmakerName
from app.domain.models.event import Event
from app.domain.models.market import MarketType, market_key
from app.domain.models.odds import OddsSnapshot


def test_bookmaker_name_enum():
    assert BookmakerName.CODERE.value == "codere"
    assert BookmakerName.PAF.value == "paf"
    assert BookmakerName.RETABET.value == "retabet"


def test_event_match_label():
    event = Event(
        external_id="123",
        home_team="Real Madrid",
        away_team="Barcelona",
        league_name="LaLiga",
        sport="soccer",
    )
    assert event.match_label == "Real Madrid vs Barcelona"


def test_event_is_frozen():
    event = Event(
        external_id="1",
        home_team="A",
        away_team="B",
        league_name="Liga",
        sport="soccer",
    )
    with pytest.raises(AttributeError):
        event.home_team = "Otro"  # type: ignore


def test_market_type_faltas():
    assert MarketType.FALTAS.value == "faltas"


def test_market_key():
    assert market_key("evt_456", "Faltas - Más") == "evt_456|Faltas - Más"


def test_odds_snapshot_creation():
    event = Event(
        external_id="99",
        home_team="Team A",
        away_team="Team B",
        league_name="Premier",
        sport="soccer",
    )
    snapshot = OddsSnapshot(
        event=event,
        market_name="Faltas - Más",
        market_type=MarketType.FALTAS,
        selection_name="Local",
        odds_value=Decimal("1.85"),
        bookmaker=BookmakerName.CODERE,
        scraped_at=datetime(2025, 3, 4, 12, 0),
    )
    assert snapshot.odds_value == Decimal("1.85")
    assert snapshot.bookmaker == BookmakerName.CODERE
    assert snapshot.event.match_label == "Team A vs Team B"
