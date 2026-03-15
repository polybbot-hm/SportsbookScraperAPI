"""Rutas de consulta de odds."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.adapters.inbound.api.dependencies import get_repository
from app.adapters.inbound.api.schemas.responses import OddsGroupedResponse, OddsItemResponse
from app.domain.ports.outbound import OddsRepositoryPort
from app.domain.services.odds_formatter import format_snapshot_for_response, format_snapshots_grouped

router = APIRouter(prefix="/odds", tags=["odds"])


@router.get(
    "",
    response_model=List[OddsItemResponse],
    summary="Listar cuotas actuales",
    description="Obtiene las cuotas más recientes. Filtros: bookmaker, league_name, event_id.",
)
def get_odds(
    bookmaker: Optional[str] = Query(None, description="Casa de apuestas"),
    league_name: Optional[str] = Query(None, description="Nombre de la liga"),
    event_id: Optional[str] = Query(None, description="ID externo del evento"),
    repository: OddsRepositoryPort = Depends(get_repository),
):
    snapshots = repository.get_latest_odds(
        bookmaker=bookmaker,
        league_name=league_name,
        event_id=event_id,
    )
    return [OddsItemResponse(**format_snapshot_for_response(s)) for s in snapshots]


@router.get(
    "/{event_id}/history",
    response_model=List[OddsItemResponse],
    summary="Histórico de cuotas de un evento",
)
def get_odds_history(
    event_id: str,
    bookmaker: Optional[str] = Query(None),
    repository: OddsRepositoryPort = Depends(get_repository),
):
    snapshots = repository.get_odds_history(event_id=event_id, bookmaker=bookmaker)
    return [OddsItemResponse(**format_snapshot_for_response(s)) for s in snapshots]
