"""Schemas Pydantic para responses (OpenAPI)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Legacy (Codere / flat model) ──────────────────────────────────────────────

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


# ── Nuevos modelos (EventSnapshot) ────────────────────────────────────────────

class SelectionResponse(BaseModel):
    key: str = Field(..., description="Clave canónica: home, draw, away, over, under…")
    name: str = Field(..., description="Nombre original de la casa")
    odds: float


class MarketResponse(BaseModel):
    market_key: str
    market_name: str
    line: Optional[float] = None
    selections: List[SelectionResponse]


class MarketCategoryResponse(BaseModel):
    category_key: str = Field(..., description="Clave canónica: resultado, totales, handicap…")
    category_name: str
    markets: List[MarketResponse]


class EventSnapshotResponse(BaseModel):
    """Snapshot completo de cuotas para un evento y bookmaker."""

    snapshot_id: str
    bookmaker: str
    scraped_at: datetime
    event_key: str = Field(..., description="Slug canónico del partido")
    home_team: str
    away_team: str
    event_date: Optional[datetime]
    competition_key: str
    market_categories: List[MarketCategoryResponse]


class OddsCompareSelectionResponse(BaseModel):
    """Cuotas de una selección comparadas entre bookmakers."""

    bookmakers: Dict[str, float] = Field(..., description="bookmaker -> cuota")
    best: Optional[str] = Field(None, description="bookmaker con la mejor cuota")


class OddsCompareMarketResponse(BaseModel):
    """Comparación de un mercado entre todas las casas."""

    market_key: str
    market_name: str
    lines: Optional[Dict[str, Dict[str, OddsCompareSelectionResponse]]] = Field(
        None, description="Para mercados con línea: línea -> selección -> comparación"
    )
    selections: Optional[Dict[str, OddsCompareSelectionResponse]] = Field(
        None, description="Para mercados sin línea: selección -> comparación"
    )


class OddsCompareCategoryResponse(BaseModel):
    category_key: str
    category_name: str
    markets: Dict[str, OddsCompareMarketResponse] = Field(
        ..., description="market_key -> comparación"
    )


class OddsCompareResponse(BaseModel):
    """Comparación completa de cuotas para un evento entre todas las casas."""

    event_key: str
    home_team: str
    away_team: str
    event_date: Optional[datetime]
    competition_key: str
    scraped_bookmakers: List[str]
    comparison: Dict[str, OddsCompareCategoryResponse] = Field(
        ..., description="category_key -> categoría con comparaciones"
    )


# ── Maestros ──────────────────────────────────────────────────────────────────

class BookmakerResponse(BaseModel):
    """Casa de apuestas disponible."""

    id: str
    name: str
    slug: str
    enabled: bool
    last_scrape: Optional[datetime] = None


class EventResponse(BaseModel):
    """Evento (partido)."""

    external_id: str
    normalized_key: str
    partido: str
    league_name: str
    sport: str
    event_date: Optional[datetime] = None


class LeagueCategoriesResponse(BaseModel):
    """Categorías de mercado disponibles por bookmaker en una liga."""

    league_key: str
    categories_by_bookmaker: Dict[str, List[str]] = Field(
        ..., description="bookmaker -> [category_keys disponibles]"
    )


# ── Scraping ──────────────────────────────────────────────────────────────────

class ScrapeStatusResponse(BaseModel):
    status: str = Field(..., description="running | completed | idle | error")
    last_run: Optional[datetime] = None
    bookmaker: Optional[str] = None
    message: Optional[str] = None


class PartidoSummary(BaseModel):
    partido: str
    event_key: str
    categorias: Dict[str, int] = Field(..., description="categoria -> nº mercados")
    total_mercados: int


class ScrapeSummaryResponse(BaseModel):
    bookmaker: str
    liga: Optional[str]
    competition_key: Optional[str]
    fecha_scraping: str
    total_eventos: int
    detalle: List[PartidoSummary]
