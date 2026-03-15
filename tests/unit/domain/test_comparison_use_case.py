"""Tests del caso de uso de comparación."""
from datetime import datetime
from decimal import Decimal

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.services.comparison_use_case import ComparisonUseCase
from tests.mocks.fake_repository import FakeOddsRepository


def _snapshot(event_id: str, partido: str, mercado: str, selection: str, cuota: float, bookmaker: BookmakerName):
    home, away = partido.split(" vs ")
    event = Event(external_id=event_id, home_team=home, away_team=away, league_name="LaLiga", sport="soccer")
    return OddsSnapshot(
        event=event,
        market_name=mercado,
        market_type=MarketType.FALTAS,
        selection_name=selection,
        odds_value=Decimal(str(cuota)),
        bookmaker=bookmaker,
        scraped_at=datetime(2025, 3, 4, 12, 0),
    )


def test_compare_by_event():
    repo = FakeOddsRepository()
    repo.snapshots = [
        _snapshot("e1", "A vs B", "Faltas", "Local", 1.85, BookmakerName.CODERE),
        _snapshot("e1", "A vs B", "Faltas", "Visitante", 2.0, BookmakerName.CODERE),
    ]
    use_case = ComparisonUseCase(repository=repo)

    result = use_case.compare_by_event("e1")

    assert len(result) == 2
    assert all(r["partido"] == "A vs B" for r in result)
    assert {r["selection"] for r in result} == {"Local", "Visitante"}


def test_compare_global_agrupa_por_casa():
    repo = FakeOddsRepository()
    repo.snapshots = [
        _snapshot("e1", "A vs B", "Faltas", "Local", 1.85, BookmakerName.CODERE),
        _snapshot("e1", "A vs B", "Faltas", "Local", 1.90, BookmakerName.PAF),
    ]
    use_case = ComparisonUseCase(repository=repo)

    result = use_case.compare_global()

    assert len(result) >= 1
    one = next(r for r in result if r["selection"] == "Local")
    assert "codere" in one["cuotas_por_casa"]
    assert "paf" in one["cuotas_por_casa"]
    assert one["cuotas_por_casa"]["codere"] == 1.85
    assert one["cuotas_por_casa"]["paf"] == 1.90
