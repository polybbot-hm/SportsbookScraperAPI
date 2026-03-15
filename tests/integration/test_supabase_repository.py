"""Tests de integración del repositorio (SQLite en memoria). Requiere sqlalchemy instalado."""
from datetime import datetime
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")
from app.adapters.outbound.persistence.supabase_repository import SupabaseRepository
from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot


@pytest.fixture
def repo():
    return SupabaseRepository("sqlite:///:memory:")


def _snapshot(event_id: str, partido: str, league: str, mercado: str, selection: str, cuota: float):
    home, away = partido.split(" vs ")
    event = Event(
        external_id=event_id,
        home_team=home,
        away_team=away,
        league_name=league,
        sport="soccer",
    )
    return OddsSnapshot(
        event=event,
        market_name=mercado,
        market_type=MarketType.FALTAS,
        selection_name=selection,
        odds_value=Decimal(str(cuota)),
        bookmaker=BookmakerName.CODERE,
        scraped_at=datetime(2025, 3, 4, 12, 0),
    )


def test_save_and_get_latest_odds(repo):
    snapshots = [
        _snapshot("e1", "A vs B", "LaLiga", "Faltas - Más", "Local", 1.85),
        _snapshot("e1", "A vs B", "LaLiga", "Faltas - Más", "Visitante", 2.0),
    ]
    repo.save_snapshots(snapshots)
    latest = repo.get_latest_odds(event_id="e1")
    assert len(latest) == 2
    assert {s.selection_name for s in latest} == {"Local", "Visitante"}
    assert latest[0].event.match_label == "A vs B"


def test_list_events(repo):
    repo.save_snapshots([
        _snapshot("e1", "A vs B", "LaLiga", "Faltas", "Local", 1.85),
        _snapshot("e2", "C vs D", "Premier", "Faltas", "Local", 1.90),
    ])
    events = repo.list_events()
    assert len(events) == 2
    events = repo.list_events(league_name="LaLiga")
    assert len(events) == 1
    assert events[0].match_label == "A vs B"


def test_upsert_and_list_leagues_with_market(repo):
    repo.upsert_league_has_market("LaLiga", "soccer", True)
    repo.upsert_league_has_market("Premier", "soccer", True)
    leagues = repo.list_leagues_with_market()
    assert "LaLiga" in leagues
    assert "Premier" in leagues
