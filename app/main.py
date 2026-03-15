"""Entrypoint FastAPI."""
from fastapi import FastAPI

from app.adapters.inbound.api.router import api_router


app = FastAPI(
    title="SportsbookScraperAPI",
    description=(
        "API para scraping de mercados de casas de apuestas deportivas. "
        "Mercados: principales, estadísticas, corners, handicap, resultado final, equipos, faltas. "
        "Casas: Codere (activo), Paf y Retabet (placeholder). "
        "Persistencia en Supabase (tabla odds_raw)."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(api_router)


@app.get("/health")
def health():
    """Comprueba que la API está viva."""
    return {"status": "ok"}
