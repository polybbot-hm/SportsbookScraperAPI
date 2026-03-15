"""Tests unitarios del DailyJobService."""
from datetime import date
from typing import List
from unittest.mock import MagicMock

import pytest

from app.domain.ports.outbound.calendar_port import CalendarPort
from app.domain.services.daily_job_service import DailyJobService


def make_calendar(match_days: List[date]) -> CalendarPort:
    mock = MagicMock(spec=CalendarPort)
    mock.get_match_days.return_value = match_days
    return mock


# ── should_run ───────────────────────────────────────────────────────────────

def test_should_run_true_when_today_is_match_day():
    today = date(2025, 3, 15)
    calendar = make_calendar([date(2025, 3, 14), date(2025, 3, 15), date(2025, 3, 22)])
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    result = service.should_run(reference_date=today)

    assert result["run"] is True
    assert result["date"] == today
    assert result["match_days_total"] == 3


def test_should_run_false_when_today_is_not_match_day():
    today = date(2025, 3, 16)
    calendar = make_calendar([date(2025, 3, 15), date(2025, 3, 22)])
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    result = service.should_run(reference_date=today)

    assert result["run"] is False
    assert result["date"] == today
    assert "omite" in result["reason"].lower()


def test_should_run_false_when_calendar_is_empty():
    today = date(2025, 3, 15)
    calendar = make_calendar([])
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    result = service.should_run(reference_date=today)

    assert result["run"] is False
    assert result["match_days_total"] == 0
    assert "vacío" in result["reason"].lower()


def test_should_run_returns_reason_on_match():
    today = date(2025, 3, 22)
    calendar = make_calendar([date(2025, 3, 22)])
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")

    result = service.should_run(reference_date=today)

    assert "Jornada detectada" in result["reason"]


# ── today() ──────────────────────────────────────────────────────────────────

def test_today_returns_a_date_object():
    calendar = make_calendar([])
    service = DailyJobService(calendar=calendar, timezone="Europe/Madrid")
    result = service.today()
    assert isinstance(result, date)


def test_today_uses_configured_timezone():
    """Verifica que today() devuelve algo coherente (no lanza ni devuelve None)."""
    calendar = make_calendar([])
    for tz in ["Europe/Madrid", "UTC", "America/New_York"]:
        service = DailyJobService(calendar=calendar, timezone=tz)
        assert isinstance(service.today(), date)
