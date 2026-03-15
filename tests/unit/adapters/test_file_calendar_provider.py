"""Tests unitarios del FileCalendarProvider."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.adapters.outbound.calendar.file_calendar_provider import FileCalendarProvider


@pytest.fixture
def calendar_file(tmp_path: Path) -> Path:
    return tmp_path / "laliga_calendar.json"


def write_calendar(path: Path, match_days: list, extra: dict = None):
    data = {"league": "Primera División", "season": "2024-25", "match_days": match_days}
    if extra:
        data.update(extra)
    path.write_text(json.dumps(data), encoding="utf-8")


# ── Casos happy path ─────────────────────────────────────────────────────────

def test_get_match_days_returns_parsed_dates(calendar_file):
    write_calendar(calendar_file, ["2025-01-18", "2025-01-19", "2025-02-01"])
    provider = FileCalendarProvider(str(calendar_file))
    days = provider.get_match_days()
    assert days == [date(2025, 1, 18), date(2025, 1, 19), date(2025, 2, 1)]


def test_has_match_today_true(calendar_file):
    write_calendar(calendar_file, ["2025-03-15"])
    provider = FileCalendarProvider(str(calendar_file))
    assert provider.has_match_today(date(2025, 3, 15)) is True


def test_has_match_today_false(calendar_file):
    write_calendar(calendar_file, ["2025-03-15"])
    provider = FileCalendarProvider(str(calendar_file))
    assert provider.has_match_today(date(2025, 3, 16)) is False


def test_ignores_invalid_date_entries(calendar_file):
    write_calendar(calendar_file, ["2025-01-18", "no-es-fecha", None, "2025-02-01"])
    provider = FileCalendarProvider(str(calendar_file))
    days = provider.get_match_days()
    assert date(2025, 1, 18) in days
    assert date(2025, 2, 1) in days
    assert len(days) == 2


# ── Casos fail-safe ──────────────────────────────────────────────────────────

def test_file_not_found_returns_empty_list(tmp_path):
    provider = FileCalendarProvider(str(tmp_path / "nonexistent.json"))
    assert provider.get_match_days() == []


def test_empty_file_returns_empty_list(calendar_file):
    calendar_file.write_text("", encoding="utf-8")
    provider = FileCalendarProvider(str(calendar_file))
    assert provider.get_match_days() == []


def test_invalid_json_returns_empty_list(calendar_file):
    calendar_file.write_text("{esto no es json", encoding="utf-8")
    provider = FileCalendarProvider(str(calendar_file))
    assert provider.get_match_days() == []


def test_missing_match_days_key_returns_empty_list(calendar_file):
    calendar_file.write_text(json.dumps({"league": "Primera División"}), encoding="utf-8")
    provider = FileCalendarProvider(str(calendar_file))
    assert provider.get_match_days() == []


def test_empty_match_days_list(calendar_file):
    write_calendar(calendar_file, [])
    provider = FileCalendarProvider(str(calendar_file))
    assert provider.get_match_days() == []
