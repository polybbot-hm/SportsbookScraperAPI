"""Puerto inbound: comparación de cuotas entre bookmakers."""
from typing import List, Optional


class ComparisonServicePort:
    """Interfaz para obtener comparativas de cuotas entre casas."""

    def compare_by_event(self, event_id: str) -> List[dict]:
        """Compara cuotas de un evento entre todas las casas. Retorna formato normalizado."""
        ...

    def compare_global(self, league_name: Optional[str] = None) -> List[dict]:
        """Compara mejores cuotas por mercado (todos los eventos)."""
        ...
