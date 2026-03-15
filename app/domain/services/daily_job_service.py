"""Servicio de dominio: decide si el job diario debe ejecutarse hoy."""
import logging
from datetime import date
from typing import Optional
from zoneinfo import ZoneInfo

from app.domain.ports.outbound.calendar_port import CalendarPort

logger = logging.getLogger(__name__)


class DailyJobService:
    """
    Encapsula la lógica de decisión para el job diario de scraping LaLiga.

    Responsabilidades:
    - Obtener la fecha actual en la zona horaria configurada.
    - Consultar el calendario para saber si hay partido.
    - Devolver un resultado estructurado con la razón de skip o ejecución.
    """

    def __init__(self, calendar: CalendarPort, timezone: str = "Europe/Madrid") -> None:
        self._calendar = calendar
        self._tz = ZoneInfo(timezone)

    def today(self) -> date:
        """Devuelve la fecha actual en la zona horaria configurada."""
        from datetime import datetime
        return datetime.now(tz=self._tz).date()

    def should_run(self, reference_date: Optional[date] = None) -> dict:
        """
        Evalúa si el job debe ejecutarse.

        Returns un dict con:
          - run (bool): True si hay partido hoy.
          - date (date): Fecha evaluada.
          - reason (str): Motivo legible para logs.
          - match_days_total (int): Total de jornadas cargadas del calendario.
        """
        evaluated_date = reference_date or self.today()
        match_days = self._calendar.get_match_days()

        if not match_days:
            return {
                "run": False,
                "date": evaluated_date,
                "reason": "Calendario vacío o no disponible — se omite el scraping.",
                "match_days_total": 0,
            }

        has_match = evaluated_date in match_days
        return {
            "run": has_match,
            "date": evaluated_date,
            "reason": (
                f"Jornada detectada para {evaluated_date}."
                if has_match
                else f"Sin partido el {evaluated_date} — se omite el scraping."
            ),
            "match_days_total": len(match_days),
        }
