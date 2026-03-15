"""Rutas de comparación de cuotas entre casas."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.adapters.inbound.api.dependencies import get_repository
from app.adapters.inbound.api.schemas.responses import CompareItemResponse, OddsItemResponse
from app.domain.ports.outbound import OddsRepositoryPort
from app.domain.services.comparison_use_case import ComparisonUseCase
from app.domain.services.odds_formatter import format_snapshot_for_response

router = APIRouter(prefix="/compare", tags=["compare"])


def get_comparison_use_case(
    repository: OddsRepositoryPort = Depends(get_repository),
) -> ComparisonUseCase:
    return ComparisonUseCase(repository=repository)


@router.get(
    "/{event_id}",
    response_model=List[OddsItemResponse],
    summary="Comparar cuotas de un evento (todas las casas)",
)
def compare_by_event(
    event_id: str,
    use_case: ComparisonUseCase = Depends(get_comparison_use_case),
):
    data = use_case.compare_by_event(event_id)
    return [OddsItemResponse(**d) for d in data]


@router.get(
    "",
    response_model=List[CompareItemResponse],
    summary="Comparación global (cuotas por casa por mercado)",
)
def compare_global(
    league_name: Optional[str] = Query(None),
    use_case: ComparisonUseCase = Depends(get_comparison_use_case),
):
    data = use_case.compare_global(league_name=league_name)
    return [CompareItemResponse(**d) for d in data]
