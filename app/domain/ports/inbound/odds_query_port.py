"""Puerto inbound: consulta de odds (listado e histórico)."""
from typing import List, Optional

from app.domain.models import OddsSnapshot


class OddsQueryPort:
    """Interfaz para consultar odds sin disparar scraping."""

    def get_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        """Obtiene las cuotas más recientes según filtros."""
        ...

    def get_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        """Obtiene histórico de cuotas de un evento."""
        ...
