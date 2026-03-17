"""Inyección de dependencias para la API."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict

import structlog
from fastapi import Depends

from app.adapters.outbound.cache.in_memory_cache import InMemoryCache
from app.adapters.outbound.scrapers.codere_scraper import CodereScraper
from app.adapters.outbound.scrapers.granmadrid_scraper import GranMadridScraper
from app.adapters.outbound.scrapers.kirol_scraper import KirolScraper
from app.adapters.outbound.scrapers.paf_scraper import PafScraper
from app.adapters.outbound.scrapers.retabet_scraper import RetabetScraper
from app.adapters.outbound.scrapers.speedy_scraper import SpeedyScraper
from app.config import Settings
from app.domain.ports.outbound import BookmakerScraperPort, OddsRepositoryPort
from app.domain.services.comparison_use_case import ComparisonUseCase
from app.domain.services.scraping_use_case import ScrapingUseCase
from app.infrastructure.config_loader import get_app_config

logger = structlog.get_logger(__name__)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_repository(settings: Settings = Depends(get_settings)) -> OddsRepositoryPort:
    """
    Repositorio en orden de prioridad:
    1. MongoOddsRepository si hay MONGO_URI en .env  ← principal
    2. SupabaseClientRepository si hay SUPABASE_URL + SUPABASE_KEY (legacy)
    3. SupabaseRepository (SQLAlchemy) si hay DATABASE_URL (legacy)
    4. InMemoryOddsRepository como fallback de desarrollo/test
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        from app.adapters.outbound.persistence.memory_repository import InMemoryOddsRepository
        return InMemoryOddsRepository()

    if settings.mongo_uri:
        try:
            from app.adapters.outbound.persistence.mongo_repository import MongoOddsRepository
            from app.infrastructure.database import get_cached_mongo_client
            app_cfg = get_app_config()
            client = get_cached_mongo_client(settings.mongo_uri)
            db = client[app_cfg.mongodb.database]
            return MongoOddsRepository(db, app_cfg.mongodb)
        except Exception as exc:
            logger.error("mongo_connection_error", error=str(exc))

    if settings.supabase_url and settings.supabase_key:
        from app.adapters.outbound.persistence.supabase_client_repository import SupabaseClientRepository
        return SupabaseClientRepository(settings.supabase_url, settings.supabase_key)

    if settings.database_url:
        from app.adapters.outbound.persistence.supabase_repository import SupabaseRepository
        return SupabaseRepository(settings.database_url)

    logger.warning("repository_fallback", reason="no persistence configured, using in-memory")
    from app.adapters.outbound.persistence.memory_repository import InMemoryOddsRepository
    return InMemoryOddsRepository()


def get_cache(settings: Settings = Depends(get_settings)) -> InMemoryCache:
    app_cfg = get_app_config()
    return InMemoryCache(ttl_seconds=app_cfg.cache.ttl_seconds)


def get_scrapers() -> Dict[str, BookmakerScraperPort]:
    """Instancia todos los scrapers disponibles y habilitados."""
    scrapers: Dict[str, BookmakerScraperPort] = {
        "codere":     CodereScraper(),
        "paf":        PafScraper(),
        "retabet":    RetabetScraper(),
        "speedy":     SpeedyScraper(),
        "granmadrid": GranMadridScraper(),
        "kirol":      KirolScraper(),
    }
    return scrapers


def get_scraping_use_case(
    scrapers: Dict[str, BookmakerScraperPort],
    repository: OddsRepositoryPort,
    cache: InMemoryCache,
) -> ScrapingUseCase:
    return ScrapingUseCase(scrapers=scrapers, repository=repository, cache=cache)


def get_comparison_use_case(repository: OddsRepositoryPort) -> ComparisonUseCase:
    return ComparisonUseCase(repository=repository)
