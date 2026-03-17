"""Rutas de casas de apuestas, eventos y datos maestros."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.inbound.api.dependencies import get_repository
from app.adapters.inbound.api.schemas.responses import (
    BookmakerResponse,
    EventResponse,
    LeagueCategoriesResponse,
)
from app.domain.models import BookmakerName
from app.domain.ports.outbound import OddsRepositoryPort
from app.infrastructure.config_loader import get_bookmaker_config, get_leagues_config

_BOOKMAKER_DISPLAY_NAMES = {
    "codere":     "Codere",
    "paf":        "PAF",
    "retabet":    "Retabet",
    "speedy":     "SpeedyBet",
    "granmadrid": "Casino Gran Madrid",
    "kirol":      "Kirolbet",
}

router = APIRouter(tags=["bookmakers"])


@router.get(
    "/bookmakers",
    response_model=List[BookmakerResponse],
    summary="Listar casas de apuestas disponibles",
)
def list_bookmakers():
    result = []
    for b in BookmakerName:
        try:
            cfg = get_bookmaker_config(b.value)
            enabled = cfg.enabled
        except Exception:
            enabled = b == BookmakerName.CODERE
        result.append(BookmakerResponse(
            id=b.value,
            name=_BOOKMAKER_DISPLAY_NAMES.get(b.value, b.value.capitalize()),
            slug=b.value,
            enabled=enabled,
        ))
    return result


@router.get(
    "/leagues",
    response_model=List[str],
    summary="Ligas configuradas",
)
def list_leagues():
    cfg = get_leagues_config()
    return list(cfg.leagues.keys())


@router.get(
    "/leagues/{league_key}/categories",
    response_model=LeagueCategoriesResponse,
    summary="Categorías de mercado disponibles por bookmaker en una liga",
)
def league_categories(
    league_key: str,
    repository: OddsRepositoryPort = Depends(get_repository),
):
    leagues_cfg = get_leagues_config()
    if not leagues_cfg.get_league(league_key):
        raise HTTPException(status_code=404, detail=f"Liga '{league_key}' no encontrada")

    if hasattr(repository, "get_available_categories"):
        categories_by_bm = repository.get_available_categories(league_key)
    else:
        categories_by_bm = {}

    return LeagueCategoriesResponse(
        league_key=league_key,
        categories_by_bookmaker=categories_by_bm,
    )


@router.get(
    "/events",
    response_model=List[EventResponse],
    summary="Listar eventos con odds disponibles",
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
            normalized_key=e.normalized_key,
            partido=e.match_label,
            league_name=e.league_name,
            sport=e.sport,
            event_date=e.event_date,
        )
        for e in events
    ]
