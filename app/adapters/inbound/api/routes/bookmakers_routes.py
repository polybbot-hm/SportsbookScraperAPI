"""Rutas de casas de apuestas y datos maestros."""
from typing import List, Optional

from fastapi import APIRouter, Depends

from app.adapters.inbound.api.dependencies import get_repository
from app.adapters.inbound.api.schemas.responses import BookmakerResponse, EventResponse
from app.domain.models import BookmakerName
from app.domain.ports.outbound import OddsRepositoryPort

router = APIRouter(tags=["bookmakers"])


@router.get(
    "/bookmakers",
    response_model=List[BookmakerResponse],
    summary="Listar casas de apuestas",
)
def list_bookmakers():
    return [
        BookmakerResponse(id=b.value, name=b.value.capitalize(), slug=b.value, active=(b == BookmakerName.CODERE))
        for b in BookmakerName
    ]


@router.get(
    "/leagues",
    response_model=List[str],
    summary="Ligas con mercado de faltas",
    description="Ligas que se sabe que tienen el mercado (cache en DB).",
)
def list_leagues(
    repository: OddsRepositoryPort = Depends(get_repository),
):
    return repository.list_leagues_with_market("faltas")


@router.get(
    "/events",
    response_model=List[EventResponse],
    summary="Listar eventos con odds",
)
def list_events(
    league_name: Optional[str] = None,
    bookmaker: Optional[str] = None,
    repository: OddsRepositoryPort = Depends(get_repository),
):
    events = repository.list_events(league_name=league_name, bookmaker=bookmaker)
    return [
        EventResponse(
            external_id=e.external_id,
            partido=e.match_label,
            league_name=e.league_name,
            sport=e.sport,
        )
        for e in events
    ]
