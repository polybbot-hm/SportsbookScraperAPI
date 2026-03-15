"""Formatea odds para salida estándar (fecha, partido, mercado, cuota)."""
from typing import Any, Dict, List

from app.domain.models import OddsSnapshot


def format_snapshot_for_response(snapshot: OddsSnapshot) -> Dict[str, Any]:
    """Un solo snapshot a dict con: fecha, partido, mercado, cuota."""
    return {
        "fecha": snapshot.scraped_at.isoformat(),
        "partido": snapshot.event.match_label,
        "mercado": snapshot.market_name,
        "cuota": float(snapshot.odds_value),
        "selection": snapshot.selection_name,
        "bookmaker": snapshot.bookmaker.value,
    }


def format_snapshots_grouped(snapshots: List[OddsSnapshot]) -> List[Dict[str, Any]]:
    """
    Agrupa snapshots por evento + mercado y devuelve lista de bloques
    con fecha, partido, mercado y cuotas (selection -> cuota).
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for s in snapshots:
        key = f"{s.event.external_id}|{s.market_name}"
        if key not in grouped:
            grouped[key] = {
                "fecha": s.scraped_at.isoformat(),
                "partido": s.event.match_label,
                "mercado": s.market_name,
                "cuotas": {},
                "bookmaker": s.bookmaker.value,
            }
        grouped[key]["cuotas"][s.selection_name] = float(s.odds_value)
    return list(grouped.values())
