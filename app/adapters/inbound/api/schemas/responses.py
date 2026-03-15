"""Schemas Pydantic para responses (OpenAPI)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OddsItemResponse(BaseModel):
    """Una cuota en formato estándar: fecha, partido, mercado, cuota."""

    fecha: str = Field(..., description="ISO timestamp del scraping")
    partido: str = Field(..., description="Local vs Visitante")
    mercado: str = Field(..., description="Nombre del mercado")
    cuota: float = Field(..., description="Valor de la cuota")
    selection: str = Field(..., description="Selección (ej: Local, Visitante)")
    bookmaker: str = Field(..., description="Casa de apuestas")


class OddsGroupedResponse(BaseModel):
    """Mercado con cuotas agrupadas por selección."""

    fecha: str
    partido: str
    mercado: str
    cuotas: Dict[str, float] = Field(..., description="selection -> cuota")
    bookmaker: str


class CompareItemResponse(BaseModel):
    """Comparación: partido, mercado, selection, cuotas por casa."""

    partido: str
    mercado: str
    selection: str
    fecha: str
    cuotas_por_casa: Dict[str, float] = Field(..., description="bookmaker -> cuota")


class BookmakerResponse(BaseModel):
    """Casa de apuestas disponible."""

    id: str
    name: str
    slug: str
    active: bool


class EventResponse(BaseModel):
    """Evento (partido)."""

    external_id: str
    partido: str
    league_name: str
    sport: str


class ScrapeStatusResponse(BaseModel):
    """Estado del último scraping."""

    status: str = Field(..., description="running | completed | idle")
    last_run: Optional[datetime] = None
    bookmaker: Optional[str] = None
    message: Optional[str] = None


class PartidoSummary(BaseModel):
    """Resumen de un partido scrapeado."""

    partido: str
    categorias: Dict[str, int] = Field(..., description="categoria -> nº mercados")
    total_mercados: int


class ScrapeSummaryResponse(BaseModel):
    """Resumen de un scraping masivo (ej: LaLiga del día)."""

    bookmaker: str
    liga: Optional[str]
    fecha_scraping: str
    total_cuotas_insertadas: int
    partidos_scrapeados: int
    detalle: List[PartidoSummary]
