"""Rutas de scraping."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.inbound.api.dependencies import (
    get_cache,
    get_repository,
    get_scrapers,
    get_settings,
)
from app.adapters.inbound.api.schemas.requests import ScrapeRequest
from app.adapters.inbound.api.schemas.responses import (
    OddsItemResponse,
    ScrapeSummaryResponse,
    ScrapeStatusResponse,
)
from app.domain.ports.outbound import OddsRepositoryPort
from app.domain.services.odds_formatter import format_snapshot_for_response
from app.domain.services.scraping_use_case import ScrapingUseCase

router = APIRouter(prefix="/scrape", tags=["scrape"])

# Estado simple del último scraping (en producción podría ser Redis/DB)
_scrape_status = {"status": "idle", "last_run": None, "bookmaker": None, "message": None}


def get_scraping_use_case(
    scrapers=Depends(get_scrapers),
    repository: OddsRepositoryPort = Depends(get_repository),
    cache=Depends(get_cache),
) -> ScrapingUseCase:
    return ScrapingUseCase(scrapers=scrapers, repository=repository, cache=cache)


@router.post(
    "",
    response_model=List[OddsItemResponse],
    summary="Scraping manual genérico",
    description=(
        "Ejecuta scraping de los mercados configurados para la casa y liga indicadas. "
        "Persiste en Supabase si DATABASE_URL está configurada."
    ),
)
def run_scrape(
    body: ScrapeRequest,
    use_case: ScrapingUseCase = Depends(get_scraping_use_case),
):
    global _scrape_status
    _scrape_status["status"] = "running"
    _scrape_status["bookmaker"] = body.bookmaker
    _scrape_status["last_run"] = datetime.utcnow()
    try:
        snapshots = use_case.run(bookmaker=body.bookmaker, league_name=body.league_name)
        _scrape_status["status"] = "completed"
        _scrape_status["message"] = f"Ok: {len(snapshots)} cuotas"
        return [OddsItemResponse(**format_snapshot_for_response(s)) for s in snapshots]
    except NotImplementedError as e:
        _scrape_status["status"] = "idle"
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        _scrape_status["status"] = "idle"
        _scrape_status["message"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/laliga-hoy",
    response_model=ScrapeSummaryResponse,
    summary="Scrapear todos los partidos de LaLiga del día",
    description=(
        "Recopila todos los partidos de Primera División de hoy, extrae las cuotas "
        "de las categorías configuradas (PRINCIPALES, ESTADÍSTICAS, CORNERS, HANDICAP, "
        "RESULTADO FINAL, EQUIPOS) e inserta en Supabase. "
        "Devuelve un resumen con el detalle por partido y categoría."
    ),
)
def scrape_laliga_hoy(
    bookmaker: str = Query(default="codere", description="Casa de apuestas (por defecto: codere)"),
    use_case: ScrapingUseCase = Depends(get_scraping_use_case),
):
    global _scrape_status
    _scrape_status["status"] = "running"
    _scrape_status["bookmaker"] = bookmaker
    _scrape_status["last_run"] = datetime.utcnow()
    try:
        summary = use_case.run_summary(
            bookmaker=bookmaker,
            league_name="Primera División",
            exact_league_match=True,
        )
        _scrape_status["status"] = "completed"
        _scrape_status["message"] = (
            f"Ok: {summary['total_cuotas_insertadas']} cuotas, "
            f"{summary['partidos_scrapeados']} partidos"
        )
        return ScrapeSummaryResponse(**summary)
    except NotImplementedError as e:
        _scrape_status["status"] = "idle"
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        _scrape_status["status"] = "idle"
        _scrape_status["message"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status",
    response_model=ScrapeStatusResponse,
    summary="Estado del último scraping",
)
def scrape_status():
    return ScrapeStatusResponse(**_scrape_status)
