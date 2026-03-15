"""Configuración de la aplicación."""
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SportsbookScraperAPI"
    debug: bool = False

    # Supabase (REST API — se usa supabase-py)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # PostgreSQL directo (opcional, alternativa a supabase_url+key)
    database_url: Optional[str] = None

    cache_ttl_seconds: int = 300
    scrape_delay_min: float = 0.3
    scrape_delay_max: float = 0.8
    scrape_cron: str = "0 */6 * * *"  # cada 6 horas

    # Cron diario LaLiga
    calendar_file_path: str = "config/laliga_calendar.json"
    job_timezone: str = "Europe/Madrid"
