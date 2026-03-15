"""Caso de uso: comparar cuotas entre bookmakers."""
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.domain.models import OddsSnapshot
from app.domain.ports.outbound import OddsRepositoryPort
from app.domain.services.odds_formatter import format_snapshot_for_response


class ComparisonUseCase:
    """Obtiene odds del repositorio y las formatea para comparación."""

    def __init__(self, repository: OddsRepositoryPort):
        self._repository = repository

    def compare_by_event(self, event_id: str) -> List[Dict[str, Any]]:
        """Compara cuotas de un evento entre todas las casas. Formato: lista por bookmaker + mercado."""
        snapshots = self._repository.get_latest_odds(event_id=event_id)
        return [format_snapshot_for_response(s) for s in snapshots]

    def compare_global(self, league_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Agrupa por evento+mercado+selection y muestra mejor cuota por bookmaker.
        Retorna lista de bloques: partido, mercado, selections con cuotas por casa.
        """
        snapshots = self._repository.get_latest_odds(league_name=league_name)
        # Agrupar por (event_id, market_name, selection_name) -> { bookmaker: odds }
        by_market_selection: Dict[tuple, Dict[str, float]] = defaultdict(dict)
        event_info: Dict[tuple, tuple] = {}  # (event_id, market_name) -> (partido, fecha)
        for s in snapshots:
            key = (s.event.external_id, s.market_name, s.selection_name)
            by_market_selection[key][s.bookmaker.value] = float(s.odds_value)
            event_key = (s.event.external_id, s.market_name)
            if event_key not in event_info:
                event_info[event_key] = (s.event.match_label, s.scraped_at.isoformat())
        result = []
        for (event_id, market_name, selection_name), bookmaker_odds in by_market_selection.items():
            event_key = (event_id, market_name)
            partido, fecha = event_info.get(event_key, ("", ""))
            result.append({
                "partido": partido,
                "mercado": market_name,
                "selection": selection_name,
                "fecha": fecha,
                "cuotas_por_casa": bookmaker_odds,
            })
        return result
