"""
Job diario de scraping LaLiga — entrypoint para Railway Cron.

Uso (Railway Cron Service):
    python -m scripts.run_laliga_daily_job

Railway Cron expression (11:00 UTC → 11:00/12:00 Europe/Madrid según DST):
    0 9 * * *   (UTC — Railway dispara en UTC, el script valida Europe/Madrid)

El script:
  1. Carga la configuración desde .env / variables de entorno.
  2. Lee el calendario desde CALENDAR_FILE_PATH.
  3. Comprueba si hoy (en JOB_TIMEZONE=Europe/Madrid) hay partido de Primera.
  4. Si NO hay partido → log y salida limpia (exit 0).
  5. Si SÍ hay partido → ejecuta scraping de LaLiga y persiste en Supabase.
  6. Devuelve exit 0 en éxito, exit 1 en error inesperado.
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("laliga_daily_job")


def build_dependencies():
    """Construye las dependencias necesarias fuera del contexto FastAPI."""
    from app.config import Settings
    from app.adapters.outbound.calendar.file_calendar_provider import FileCalendarProvider
    from app.adapters.outbound.cache.in_memory_cache import InMemoryCache
    from app.adapters.outbound.scrapers.codere_scraper import CodereScraper
    from app.adapters.outbound.scrapers.paf_scraper import PafScraper
    from app.adapters.outbound.scrapers.retabet_scraper import RetabetScraper
    from app.domain.services.daily_job_service import DailyJobService
    from app.domain.services.scraping_use_case import ScrapingUseCase

    settings = Settings()

    calendar = FileCalendarProvider(settings.calendar_file_path)
    job_service = DailyJobService(calendar=calendar, timezone=settings.job_timezone)

    # Repositorio en orden de prioridad (igual que la API)
    if settings.supabase_url and settings.supabase_key:
        from app.adapters.outbound.persistence.supabase_client_repository import SupabaseClientRepository
        repository = SupabaseClientRepository(settings.supabase_url, settings.supabase_key)
    elif settings.database_url:
        from app.adapters.outbound.persistence.supabase_repository import SupabaseRepository
        repository = SupabaseRepository(settings.database_url)
    else:
        logger.warning(
            "No se encontraron credenciales de base de datos. "
            "Las cuotas se guardarán solo en memoria (no persisten)."
        )
        from app.adapters.outbound.persistence.memory_repository import InMemoryOddsRepository
        repository = InMemoryOddsRepository()

    cache = InMemoryCache(ttl_seconds=settings.cache_ttl_seconds)

    scrapers = {
        "codere": CodereScraper(),
        "paf": PafScraper(),
        "retabet": RetabetScraper(),
    }

    use_case = ScrapingUseCase(scrapers=scrapers, repository=repository, cache=cache)

    return job_service, use_case


def main() -> int:
    logger.info("=== Job diario LaLiga iniciado ===")

    try:
        job_service, use_case = build_dependencies()
    except Exception as exc:
        logger.error("Error inicializando dependencias: %s", exc, exc_info=True)
        return 1

    decision = job_service.should_run()
    logger.info(
        "Fecha evaluada: %s | Jornadas en calendario: %d | ¿Ejecutar?: %s",
        decision["date"],
        decision["match_days_total"],
        decision["run"],
    )
    logger.info("Motivo: %s", decision["reason"])

    if not decision["run"]:
        logger.info("=== Job omitido — sin partido hoy ===")
        return 0

    logger.info("Iniciando scraping de Primera División (Codere)…")
    try:
        summary = use_case.run_summary(
            bookmaker="codere",
            league_name="Primera División",
            exact_league_match=True,
        )
        logger.info(
            "Scraping completado: %d cuotas insertadas en %d partidos.",
            summary["total_cuotas_insertadas"],
            summary["partidos_scrapeados"],
        )
        for partido in summary.get("detalle", []):
            logger.info(
                "  - %s: %d mercados (%s)",
                partido["partido"],
                partido["total_mercados"],
                ", ".join(f"{k}={v}" for k, v in partido["categorias"].items()),
            )
        logger.info("=== Job finalizado con éxito ===")
        return 0

    except Exception as exc:
        logger.error("Error durante el scraping: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
