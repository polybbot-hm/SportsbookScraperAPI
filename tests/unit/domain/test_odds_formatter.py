"""Tests del formateador de odds."""
from datetime import datetime
from decimal import Decimal

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.services.odds_formatter import format_snapshot_for_response, format_snapshots_grouped


def _make_snapshot(partido: str, mercado: str, selection: str, cuota: float, bookmaker: BookmakerName = BookmakerName.CODERE):
    home, away = partido.split(" vs ")
    event = Event(external_id="1", home_team=home, away_team=away, league_name="LaLiga", sport="soccer")
    return OddsSnapshot(
        event=event,
        market_name=mercado,
        market_type=MarketType.FALTAS,
        selection_name=selection,
        odds_value=Decimal(str(cuota)),
        bookmaker=bookmaker,
        scraped_at=datetime(2025, 3, 4, 12, 0),
    )


def test_format_snapshot_for_response():
    s = _make_snapshot("A vs B", "Faltas - Más", "Local", 1.85)
    out = format_snapshot_for_response(s)
    assert out["partido"] == "A vs B"
    assert out["mercado"] == "Faltas - Más"
    assert out["cuota"] == 1.85
    assert out["selection"] == "Local"
    assert out["bookmaker"] == "codere"
    assert "fecha" in out


def test_format_snapshots_grouped():
    s1 = _make_snapshot("A vs B", "Faltas - Más", "Local", 1.85)
    s2 = _make_snapshot("A vs B", "Faltas - Más", "Visitante", 2.10)
    grouped = format_snapshots_grouped([s1, s2])
    assert len(grouped) == 1
    assert grouped[0]["partido"] == "A vs B"
    assert grouped[0]["cuotas"]["Local"] == 1.85
    assert grouped[0]["cuotas"]["Visitante"] == 2.10
