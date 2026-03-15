"""Puerto (interfaz) para el proveedor de calendario de competición."""
from abc import ABC, abstractmethod
from datetime import date
from typing import List


class CalendarPort(ABC):
    """Contrato para obtener las fechas en que hay partido de una competición."""

    @abstractmethod
    def get_match_days(self) -> List[date]:
        """Devuelve la lista de fechas con partido."""
        ...

    def has_match_today(self, today: date) -> bool:
        """Indica si la fecha dada es jornada de competición."""
        return today in self.get_match_days()
