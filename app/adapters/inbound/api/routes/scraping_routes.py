"""Rutas de scraping."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.inbound.api.dependencies import (
    get_cache,
    get_repository,
    get_scrapers,
    get_settings,
)
from app.adapters.inbound.api.schemas.requests import ScrapeRequest
from app.adapters.inbound.api.schemas.responses import (
    MarketCategoryResponse,
    MarketResponse,
    OddsItemResponse,
    PartidoSummary,
    ScrapeSummaryResponse,
    ScrapeStatusResponse,
    SelectionResponse,
)
from app.domain.exceptions import EventsNotFoundError, ScrapingError, TokenCaptureError
from app.domain.models.event_snapshot import EventSnapshot
from app.domain.ports.outbound import OddsRepositoryPort
from app.domain.services.odds_formatter import format_snapshot_for_response
from app.domain.services.scraping_use_case import ScrapingUseCase
from app.infrastructure.config_loader import get_bookmaker_config, get_leagues_config

router = APIRouter(prefix="/scrape", tags=["scrape"])
logger = structlog.get_logger(__name__)

_scrape_status = {"status": "idle", "last_run": None, "bookmaker": None, "message": None}


def get_scraping_use_case(
    scrapers=Depends(get_scrapers),
    repository: OddsRepositoryPort = Depends(get_repository),
    cache=Depends(get_cache),
) -> ScrapingUseCase:
    return ScrapingUseCase(scrapers=scrapers, repository=repository, cache=cache)


# ── Helpers de serialización ──────────────────────────────────────────────────

def _snapshot_to_response_categories(snapshot: EventSnapshot) -> List[MarketCategoryResponse]:
    return [
        MarketCategoryResponse(
            category_key=cat.category_key,
            category_name=cat.category_name,
            markets=[
                MarketResponse(
                    market_key=m.market_key,
                    market_name=m.market_name,
                    line=m.line,
                    selections=[
                        SelectionResponse(key=s.key, name=s.name, odds=s.odds)
                        for s in m.selections
                    ],
                )
                for m in cat.markets
            ],
        )
        for cat in snapshot.market_categories
    ]


# ── Endpoint: scrape genérico (legacy Codere) ─────────────────────────────────

@router.post(
    "",
    response_model=List[OddsItemResponse],
    summary="Scraping manual genérico (modelo legacy)",
    description="Ejecuta scraping flat (Codere). Para los nuevos bookmakers usa /scrape/liga.",
)
def run_scrape(
    body: ScrapeRequest,
    use_case: ScrapingUseCase = Depends(get_scraping_use_case),
):
    global _scrape_status
    _scrape_status.update({"status": "running", "bookmaker": body.bookmaker, "last_run": datetime.now(timezone.utc)})
    try:
        snapshots = use_case.run(bookmaker=body.bookmaker, league_name=body.league_name)
        _scrape_status.update({"status": "completed", "message": f"Ok: {len(snapshots)} cuotas"})
        return [OddsItemResponse(**format_snapshot_for_response(s)) for s in snapshots]
    except NotImplementedError as exc:
        _scrape_status["status"] = "idle"
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        _scrape_status.update({"status": "error", "message": str(exc)})
        logger.error("scrape_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── Endpoint: scrape de liga completa (nuevos scrapers) ───────────────────────

@router.post(
    "/liga",
    response_model=ScrapeSummaryResponse,
    summary="Scrapear liga completa con los nuevos scrapers",
    description=(
        "Ejecuta scraping de todos los eventos de una liga para uno o todos los bookmakers "
        "nuevos (speedy, granmadrid, kirol). Persiste EventSnapshots en MongoDB."
    ),
)
def scrape_liga(
    bookmaker: str = Query(
        ...,
        description="Casa de apuestas: speedy | granmadrid | kirol",
    ),
    league_key: Optional[str] = Query(
        None,
        description="Clave de liga (ej: la_liga). Por defecto usa la liga activa del YAML.",
    ),
    scrapers=Depends(get_scrapers),
    repository: OddsRepositoryPort = Depends(get_repository),
):
    global _scrape_status
    _scrape_status.update({"status": "running", "bookmaker": bookmaker, "last_run": datetime.now(timezone.utc)})

    try:
        leagues_cfg = get_leagues_config()
        active_key = league_key or leagues_cfg.active_league
        league_cfg = leagues_cfg.get_league(active_key)
        if not league_cfg:
            raise HTTPException(status_code=404, detail=f"Liga '{active_key}' no encontrada en leagues.yaml")

        scraper = scrapers.get(bookmaker)
        if not scraper:
            raise HTTPException(status_code=404, detail=f"Bookmaker '{bookmaker}' no encontrado")

        bm_cfg = get_bookmaker_config(bookmaker)
        snapshots: list[EventSnapshot] = scraper.scrape_event_snapshots(
            competition_key=active_key,
            bookmaker_cfg=bm_cfg,
            league_cfg=league_cfg,
        )

        if hasattr(repository, "save_event_snapshots"):
            repository.save_event_snapshots(snapshots)
        else:
            logger.warning("repository_no_event_snapshots", bookmaker=bookmaker)

        detalle = [
            PartidoSummary(
                partido=s.event.match_label,
                event_key=s.event.normalized_key,
                categorias={cat.category_key: cat.total_markets for cat in s.market_categories},
                total_mercados=s.total_markets,
            )
            for s in snapshots
        ]

        msg = f"Ok: {len(snapshots)} eventos"
        _scrape_status.update({"status": "completed", "message": msg})

        return ScrapeSummaryResponse(
            bookmaker=bookmaker,
            liga=league_cfg.name,
            competition_key=active_key,
            fecha_scraping=datetime.now(timezone.utc).isoformat(),
            total_eventos=len(snapshots),
            detalle=detalle,
        )

    except HTTPException:
        _scrape_status["status"] = "idle"
        raise
    except (TokenCaptureError, EventsNotFoundError) as exc:
        _scrape_status.update({"status": "error", "message": str(exc)})
        logger.warning("scrape_partial_error", error=str(exc), context=exc.context)
        raise HTTPException(status_code=502, detail=str(exc))
    except ScrapingError as exc:
        _scrape_status.update({"status": "error", "message": str(exc)})
        logger.error("scrape_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        _scrape_status.update({"status": "error", "message": str(exc)})
        logger.error("scrape_unexpected_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── Endpoint: LaLiga del día (legacy Codere) ──────────────────────────────────

@router.post(
    "/laliga-hoy",
    response_model=ScrapeSummaryResponse,
    summary="Scrapear LaLiga del día (Codere, modelo legacy)",
)
def scrape_laliga_hoy(
    bookmaker: str = Query(default="codere"),
    use_case: ScrapingUseCase = Depends(get_scraping_use_case),
):
    global _scrape_status
    _scrape_status.update({"status": "running", "bookmaker": bookmaker, "last_run": datetime.now(timezone.utc)})
    try:
        summary = use_case.run_summary(
            bookmaker=bookmaker,
            league_name="Primera División",
            exact_league_match=True,
        )
        _scrape_status.update({"status": "completed", "message": f"Ok: {summary.get('partidos_scrapeados', 0)} partidos"})
        return ScrapeSummaryResponse(
            bookmaker=summary["bookmaker"],
            liga=summary.get("liga"),
            competition_key=None,
            fecha_scraping=summary["fecha_scraping"],
            total_eventos=summary.get("partidos_scrapeados", 0),
            detalle=[
                PartidoSummary(
                    partido=p["partido"],
                    event_key="",
                    categorias=p["categorias"],
                    total_mercados=p["total_mercados"],
                )
                for p in summary.get("detalle", [])
            ],
        )
    except NotImplementedError as exc:
        _scrape_status["status"] = "idle"
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        _scrape_status.update({"status": "error", "message": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", response_model=ScrapeStatusResponse, summary="Estado del último scraping")
def scrape_status():
    return ScrapeStatusResponse(**_scrape_status)
