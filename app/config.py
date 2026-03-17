"""Configuración de la aplicación — solo secretos y variables de entorno.
La configuración estructural (delays, mappings, IDs) vive en config/*.yaml.
"""
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SportsbookScraperAPI"
    debug: bool = False

    # MongoDB (principal)
    mongo_uri: Optional[str] = None

    # Supabase — mantenido para compatibilidad hacia atrás
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # PostgreSQL directo (alternativa legacy)
    database_url: Optional[str] = None

    # Paths de configuración YAML (override por entorno)
    app_config_path: str = "config/app.yaml"
    leagues_config_path: str = "config/leagues.yaml"
    bookmakers_config_dir: str = "config/bookmakers"

    # Cron diario LaLiga (override de app.yaml si se necesita)
    job_timezone: str = "Europe/Madrid"
