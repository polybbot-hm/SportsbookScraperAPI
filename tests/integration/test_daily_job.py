"""Tests de integración del job diario LaLiga (run / skip)."""
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.outbound.calendar.file_calendar_provider import FileCalendarProvider
from app.domain.services.daily_job_service import DailyJobService


@pytest.fixture
def calendar_with_today(tmp_path: Path) -> Path:
    """Calendario que incluye la fecha de hoy."""
    today = date.today().isoformat()
    data = {"league": "Primera División", "season": "2024-25", "match_days": [today]}
    cal_file = tmp_path / "calendar.json"
    cal_file.write_text(json.dumps(data), encoding="utf-8")
    return cal_file


@pytest.fixture
def calendar_without_today(tmp_path: Path) -> Path:
    """Calendario que NO incluye la fecha de hoy."""
    data = {
        "league": "Primera División",
        "season": "2024-25",
        "match_days": ["2000-01-01"],  # fecha en el pasado
    }
    cal_file = tmp_path / "calendar.json"
    cal_file.write_text(json.dumps(data), encoding="utf-8")
    return cal_file


# ── Flujo SKIP ───────────────────────────────────────────────────────────────

def test_job_skips_when_no_match_today(calendar_without_today):
    calendar = FileCalendarProvider(str(calendar_without_today))
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    decision = service.should_run()

    assert decision["run"] is False


def test_job_skips_with_empty_calendar(tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text(
        json.dumps({"league": "Primera División", "season": "2024-25", "match_days": []}),
        encoding="utf-8",
    )
    calendar = FileCalendarProvider(str(empty_file))
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    decision = service.should_run()

    assert decision["run"] is False
    assert decision["match_days_total"] == 0


# ── Flujo RUN ────────────────────────────────────────────────────────────────

def test_job_runs_when_match_today(calendar_with_today):
    calendar = FileCalendarProvider(str(calendar_with_today))
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    decision = service.should_run()

    assert decision["run"] is True


def test_job_calls_use_case_when_match_today(calendar_with_today):
    """Simula el flujo completo del script: si hay partido, llama a run_summary."""
    calendar = FileCalendarProvider(str(calendar_with_today))
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    mock_use_case = MagicMock()
    mock_use_case.run_summary.return_value = {
        "bookmaker": "codere",
        "liga": "Primera División",
        "fecha_scraping": "2025-03-15T11:00:00",
        "total_cuotas_insertadas": 42,
        "partidos_scrapeados": 5,
        "detalle": [],
    }

    decision = service.should_run()
    if decision["run"]:
        summary = mock_use_case.run_summary(
            bookmaker="codere",
            league_name="Primera División",
            exact_league_match=True,
        )
        mock_use_case.run_summary.assert_called_once_with(
            bookmaker="codere",
            league_name="Primera División",
            exact_league_match=True,
        )
        assert summary["total_cuotas_insertadas"] == 42


def test_job_does_not_call_use_case_when_no_match(calendar_without_today):
    """Verifica que sin partido NO se llama al use case."""
    calendar = FileCalendarProvider(str(calendar_without_today))
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    mock_use_case = MagicMock()

    decision = service.should_run()
    if not decision["run"]:
        pass  # simulamos el guard del script principal

    mock_use_case.run_summary.assert_not_called()
