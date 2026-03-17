"""Entrypoint FastAPI."""
from fastapi import FastAPI

from app.adapters.inbound.api.router import api_router
from app.infrastructure.config_loader import get_app_config
from app.infrastructure.logging_config import configure_logging

# Inicializar logging desde config/app.yaml al arrancar
try:
    _app_cfg = get_app_config()
    configure_logging(
        level=_app_cfg.logging.level,
        fmt=_app_cfg.logging.format,
        output=_app_cfg.logging.output,
        file_path=_app_cfg.logging.file_path,
    )
except Exception:
    configure_logging()  # fallback con valores por defecto


app = FastAPI(
    title="SportsbookScraperAPI",
    description=(
        "API para scraping de mercados de casas de apuestas deportivas. "
        "Casas: Codere, SpeedyBet, Casino Gran Madrid, Kirolbet (+ PAF, Retabet). "
        "Modelo de datos: categorías canónicas de mercado con submercados y selecciones. "
        "Persistencia en MongoDB. Configuración centralizada en YAML."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(api_router)


@app.get("/health")
def health():
    """Comprueba que la API está viva."""
    return {"status": "ok", "version": "0.2.0"}
