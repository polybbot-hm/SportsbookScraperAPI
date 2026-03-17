"""Rutas de comparación de cuotas entre casas."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.inbound.api.dependencies import get_repository
from app.adapters.inbound.api.schemas.responses import (
    CompareItemResponse,
    OddsCompareMarketResponse,
    OddsCompareCategoryResponse,
    OddsCompareResponse,
    OddsCompareSelectionResponse,
    OddsItemResponse,
)
from app.domain.models.market_category import CATEGORY_DISPLAY_NAMES
from app.domain.ports.outbound import OddsRepositoryPort
from app.domain.services.comparison_use_case import ComparisonUseCase
from app.domain.services.odds_formatter import format_snapshot_for_response

router = APIRouter(prefix="/compare", tags=["compare"])
logger = structlog.get_logger(__name__)


def get_comparison_use_case(
    repository: OddsRepositoryPort = Depends(get_repository),
) -> ComparisonUseCase:
    return ComparisonUseCase(repository=repository)


# ── Comparación nueva (EventSnapshot) ────────────────────────────────────────

@router.get(
    "/event/{event_key}",
    response_model=OddsCompareResponse,
    summary="Comparar cuotas de un evento entre todas las casas",
    description=(
        "Para un event_key canónico (ej: villarreal-cf_real-sociedad_20260320) devuelve "
        "las cuotas de todos los bookmakers agrupadas por categoría > mercado > selección, "
        "indicando qué casa ofrece la mejor cuota en cada selección."
    ),
)
def compare_event_snapshots(
    event_key: str,
    bookmakers: Optional[str] = Query(None, description="Filtrar por bookmakers (csv: speedy,kirol)"),
    categories: Optional[str] = Query(None, description="Filtrar por categorías (csv: resultado,totales)"),
    repository: OddsRepositoryPort = Depends(get_repository),
):
    if not hasattr(repository, "get_latest_event_snapshots"):
        raise HTTPException(
            status_code=501,
            detail="El repositorio actual no soporta EventSnapshots. Configura MONGO_URI.",
        )

    from app.domain.models.bookmaker import BookmakerName
    bm_filter = None
    if bookmakers:
        try:
            bm_filter = [BookmakerName(b.strip()) for b in bookmakers.split(",")]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Bookmaker inválido: {exc}")

    cat_filter = [c.strip() for c in categories.split(",")] if categories else None

    snapshots = repository.get_latest_event_snapshots(
        event_key=event_key,
        bookmakers=bm_filter,
        category_keys=cat_filter,
    )

    if not snapshots:
        raise HTTPException(status_code=404, detail=f"Sin datos para event_key='{event_key}'")

    # Construir comparación: cat -> market_key+(line) -> selection_key -> {bm: odds}
    # Estructura: {cat_key: {market_key: {line?: {sel_key: {bm: odds}}}}}
    cat_data: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    cat_names: dict[str, str] = {}
    market_names: dict[tuple, str] = {}

    event_ref = snapshots[0].event
    scraped_bookmakers = []

    for snapshot in snapshots:
        bm = snapshot.bookmaker.value
        scraped_bookmakers.append(bm)
        for cat in snapshot.market_categories:
            cat_names[cat.category_key] = cat.category_name
            for market in cat.markets:
                line_key = str(market.line) if market.line is not None else "__no_line__"
                mk_tuple = (cat.category_key, market.market_key, line_key)
                market_names[mk_tuple] = market.market_name
                for sel in market.selections:
                    cat_data[cat.category_key][(market.market_key, line_key)][sel.key][bm] = sel.odds

    comparison: Dict[str, OddsCompareCategoryResponse] = {}
    for cat_key, markets_dict in cat_data.items():
        markets_response: Dict[str, OddsCompareMarketResponse] = {}

        has_lines: dict[str, bool] = {}
        for (mkt_key, line_key), _ in markets_dict.items():
            if mkt_key not in has_lines:
                has_lines[mkt_key] = False
            if line_key != "__no_line__":
                has_lines[mkt_key] = True

        grouped_by_mkt: dict[str, dict] = defaultdict(dict)
        for (mkt_key, line_key), sels in markets_dict.items():
            grouped_by_mkt[mkt_key][line_key] = sels

        for mkt_key, lines_data in grouped_by_mkt.items():
            if has_lines.get(mkt_key):
                # Con líneas
                lines_resp: Dict[str, Dict[str, OddsCompareSelectionResponse]] = {}
                for line_key, sels in lines_data.items():
                    if line_key == "__no_line__":
                        continue
                    lines_resp[line_key] = {
                        sel_key: OddsCompareSelectionResponse(
                            bookmakers=bm_odds,
                            best=max(bm_odds, key=bm_odds.get) if bm_odds else None,
                        )
                        for sel_key, bm_odds in sels.items()
                    }
                example_line_key = next(iter(lines_data))
                mkt_name = market_names.get((cat_key, mkt_key, example_line_key), mkt_key)
                markets_response[mkt_key] = OddsCompareMarketResponse(
                    market_key=mkt_key,
                    market_name=mkt_name,
                    lines=lines_resp,
                )
            else:
                sels = lines_data.get("__no_line__", {})
                mkt_name = market_names.get((cat_key, mkt_key, "__no_line__"), mkt_key)
                markets_response[mkt_key] = OddsCompareMarketResponse(
                    market_key=mkt_key,
                    market_name=mkt_name,
                    selections={
                        sel_key: OddsCompareSelectionResponse(
                            bookmakers=bm_odds,
                            best=max(bm_odds, key=bm_odds.get) if bm_odds else None,
                        )
                        for sel_key, bm_odds in sels.items()
                    },
                )

        comparison[cat_key] = OddsCompareCategoryResponse(
            category_key=cat_key,
            category_name=cat_names.get(cat_key, CATEGORY_DISPLAY_NAMES.get(cat_key, cat_key)),
            markets=markets_response,
        )

    return OddsCompareResponse(
        event_key=event_key,
        home_team=event_ref.home_team,
        away_team=event_ref.away_team,
        event_date=event_ref.event_date,
        competition_key=snapshots[0].competition.normalized_key,
        scraped_bookmakers=scraped_bookmakers,
        comparison=comparison,
    )


# ── Comparación legacy (OddsSnapshot flat) ───────────────────────────────────

@router.get(
    "/{event_id}",
    response_model=List[OddsItemResponse],
    summary="Comparar cuotas de un evento (modelo legacy Codere)",
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
    summary="Comparación global (modelo legacy)",
)
def compare_global(
    league_name: Optional[str] = Query(None),
    use_case: ComparisonUseCase = Depends(get_comparison_use_case),
):
    data = use_case.compare_global(league_name=league_name)
    return [CompareItemResponse(**d) for d in data]
