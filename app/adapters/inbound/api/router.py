"""Router principal de la API v1."""
from fastapi import APIRouter

from app.adapters.inbound.api.routes import (
    bookmakers_router,
    comparison_router,
    odds_router,
    scraping_router,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(scraping_router)
api_router.include_router(odds_router)
api_router.include_router(comparison_router)
api_router.include_router(bookmakers_router)
