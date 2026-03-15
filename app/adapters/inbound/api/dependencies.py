"""Inyección de dependencias para la API."""
from functools import lru_cache
import os
from typing import Dict

from fastapi import Depends

from app.adapters.outbound.cache.in_memory_cache import InMemoryCache
from app.adapters.outbound.scrapers.codere_scraper import CodereScraper
from app.adapters.outbound.scrapers.paf_scraper import PafScraper
from app.adapters.outbound.scrapers.retabet_scraper import RetabetScraper
from app.config import Settings
from app.domain.ports.outbound import BookmakerScraperPort, OddsRepositoryPort
from app.domain.services.comparison_use_case import ComparisonUseCase
from app.domain.services.scraping_use_case import ScrapingUseCase


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_repository(settings: Settings = Depends(get_settings)) -> OddsRepositoryPort:
    """
    Repositorio en orden de prioridad:
    1. SupabaseClientRepository si hay SUPABASE_URL + SUPABASE_KEY (.env)
    2. SupabaseRepository (SQLAlchemy) si hay DATABASE_URL
    3. InMemoryOddsRepository como fallback de desarrollo
    """
    # En tests forzamos repositorio en memoria para no depender de datos reales.
    if os.getenv("PYTEST_CURRENT_TEST"):
        from app.adapters.outbound.persistence.memory_repository import InMemoryOddsRepository
        return InMemoryOddsRepository()

    if settings.supabase_url and settings.supabase_key:
        from app.adapters.outbound.persistence.supabase_client_repository import SupabaseClientRepository
        return SupabaseClientRepository(settings.supabase_url, settings.supabase_key)
    if settings.database_url:
        from app.adapters.outbound.persistence.supabase_repository import SupabaseRepository
        return SupabaseRepository(settings.database_url)
    from app.adapters.outbound.persistence.memory_repository import InMemoryOddsRepository
    return InMemoryOddsRepository()


def get_cache(settings: Settings = Depends(get_settings)) -> InMemoryCache:
    return InMemoryCache(ttl_seconds=settings.cache_ttl_seconds)


def get_scrapers() -> Dict[str, BookmakerScraperPort]:
    return {
        "codere": CodereScraper(),
        "paf": PafScraper(),
        "retabet": RetabetScraper(),
    }


def get_scraping_use_case(
    scrapers: Dict[str, BookmakerScraperPort],
    repository: OddsRepositoryPort,
    cache: InMemoryCache,
) -> ScrapingUseCase:
    return ScrapingUseCase(scrapers=scrapers, repository=repository, cache=cache)


def get_comparison_use_case(repository: OddsRepositoryPort) -> ComparisonUseCase:
    return ComparisonUseCase(repository=repository)
