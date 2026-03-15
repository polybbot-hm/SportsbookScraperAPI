"""Schemas Pydantic para requests."""
from typing import Optional

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    """Request para lanzar scraping manual."""

    bookmaker: str = Field(..., description="Casa de apuestas: codere, paf, retabet")
    league_name: Optional[str] = Field(None, description="Filtrar por liga; si se omite, todas las ligas con mercado")


class OddsQueryParams(BaseModel):
    """Query params para GET /odds."""

    bookmaker: Optional[str] = None
    league_name: Optional[str] = None
    event_id: Optional[str] = None


class CompareQueryParams(BaseModel):
    """Query params para GET /compare."""

    league_name: Optional[str] = None
