"""Puerto para persistencia de odds y eventos."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from app.domain.models import Event, OddsSnapshot


class OddsRepositoryPort(ABC):
    """Contrato para guardar y consultar odds y eventos."""

    @abstractmethod
    def save_snapshots(self, snapshots: List[OddsSnapshot]) -> None:
        """Persiste una lista de snapshots de cuotas (y eventos/mercados si no existen)."""
        ...

    @abstractmethod
    def get_latest_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        """Obtiene las cuotas más recientes según filtros."""
        ...

    @abstractmethod
    def get_odds_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[OddsSnapshot]:
        """Obtiene el histórico de cuotas de un evento."""
        ...

    @abstractmethod
    def list_events(
        self,
        league_name: Optional[str] = None,
        bookmaker: Optional[str] = None,
    ) -> List[Event]:
        """Lista eventos con odds disponibles."""
        ...

    @abstractmethod
    def list_leagues_with_market(self, market_type: str = "faltas") -> List[str]:
        """Lista nombres de ligas que tienen el mercado (para no scrapear ligas sin mercado)."""
        ...

    @abstractmethod
    def upsert_league_has_market(self, league_name: str, sport: str, has_market: bool) -> None:
        """Actualiza si una liga tiene o no el mercado (cache en DB)."""
        ...
