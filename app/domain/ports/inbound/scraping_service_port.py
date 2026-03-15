"""Puerto inbound: orquestación del scraping."""
from typing import List, Optional

from app.domain.models import OddsSnapshot


class ScrapingServicePort:
    """Interfaz que expone el caso de uso de scraping a la API/scheduler."""

    def run_scrape(
        self,
        bookmaker: str,
        league_name: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        """
        Ejecuta el scraping para una casa de apuestas.
        league_name opcional: si se pasa, solo esa liga; si no, todas las que tengan mercado.
        """
        ...
