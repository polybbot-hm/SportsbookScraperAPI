"""Proveedor de calendario basado en fichero JSON local."""
import json
import logging
from datetime import date
from pathlib import Path
from typing import List

from app.domain.ports.outbound.calendar_port import CalendarPort

logger = logging.getLogger(__name__)


class FileCalendarProvider(CalendarPort):
    """
    Lee las fechas de jornada desde un fichero JSON con la estructura:

    {
      "league": "Primera División",
      "season": "2024-25",
      "match_days": ["2025-01-18", "2025-01-19", ...]
    }

    Si el fichero no existe, está vacío o tiene formato incorrecto,
    devuelve lista vacía (fail-safe: nunca lanza excepción en producción).
    """

    def __init__(self, file_path: str) -> None:
        self._file_path = Path(file_path)

    def get_match_days(self) -> List[date]:
        if not self._file_path.exists():
            logger.warning("Fichero de calendario no encontrado: %s", self._file_path)
            return []

        try:
            raw = self._file_path.read_text(encoding="utf-8").strip()
            if not raw:
                logger.warning("Fichero de calendario vacío: %s", self._file_path)
                return []

            data = json.loads(raw)
            raw_dates = data.get("match_days", [])

            parsed: List[date] = []
            for entry in raw_dates:
                try:
                    parsed.append(date.fromisoformat(str(entry)))
                except (ValueError, TypeError):
                    logger.warning("Fecha inválida en calendario, se ignora: %r", entry)

            logger.debug("Calendario cargado: %d fechas desde %s", len(parsed), self._file_path)
            return parsed

        except json.JSONDecodeError as exc:
            logger.error("Error parseando calendario JSON (%s): %s", self._file_path, exc)
            return []
        except Exception as exc:
            logger.error("Error inesperado leyendo calendario (%s): %s", self._file_path, exc)
            return []
