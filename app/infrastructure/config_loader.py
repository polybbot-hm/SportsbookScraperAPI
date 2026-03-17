"""Cargador centralizado de configuración desde archivos YAML."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, field_validator, model_validator

from app.domain.exceptions import InvalidConfigError, MissingConfigError


# ── Modelos Pydantic para validación ──────────────────────────────────────────

class RetryConfig(BaseModel):
    max_attempts: int = 3
    wait_min: float = 1.0
    wait_max: float = 5.0


class ScrapingConfig(BaseModel):
    delay_min: float = 0.3
    delay_max: float = 0.8
    cron: str = "0 */6 * * *"
    retry: RetryConfig = RetryConfig()


class MongoConfig(BaseModel):
    database: str = "sportsbook_scraper"
    collection_snapshots: str = "odds_snapshots"
    collection_events: str = "events"


class CacheConfig(BaseModel):
    ttl_seconds: int = 300


class CalendarConfig(BaseModel):
    file_path: str = "config/laliga_calendar.json"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"    # json | console
    output: str = "stdout"  # stdout | file
    file_path: str = "logs/app.log"

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"logging.level debe ser uno de {allowed}")
        return upper

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in ("json", "console"):
            raise ValueError("logging.format debe ser 'json' o 'console'")
        return v


class AppConfig(BaseModel):
    name: str = "SportsbookScraperAPI"
    debug: bool = False
    timezone: str = "Europe/Madrid"
    scraping: ScrapingConfig = ScrapingConfig()
    mongodb: MongoConfig = MongoConfig()
    cache: CacheConfig = CacheConfig()
    calendar: CalendarConfig = CalendarConfig()
    logging: LoggingConfig = LoggingConfig()


# ── Configuración de ligas ────────────────────────────────────────────────────

class LeagueBookmakerConfig(BaseModel):
    """Identificadores de la competición en cada casa de apuestas."""

    group_id: Optional[int] = None         # SpeedyBet (Kambi)
    champ_id: Optional[int] = None         # Gran Madrid (Altenar)
    competition_id: Optional[int] = None   # Kirolbet (HTML)
    sport_handle: Optional[str] = None     # Codere
    league_handle: Optional[str] = None    # Codere

    @property
    def is_configured(self) -> bool:
        """True si al menos un identificador tiene valor."""
        return any(
            v is not None
            for v in [self.group_id, self.champ_id, self.competition_id, self.sport_handle]
        )


class LeagueConfig(BaseModel):
    name: str
    sport: str = "football"
    bookmakers: dict[str, LeagueBookmakerConfig] = {}

    def get_bookmaker(self, bookmaker_key: str) -> Optional[LeagueBookmakerConfig]:
        return self.bookmakers.get(bookmaker_key)


class LeaguesConfig(BaseModel):
    active_league: str
    leagues: dict[str, LeagueConfig]

    def get_active(self) -> LeagueConfig:
        if self.active_league not in self.leagues:
            raise MissingConfigError(
                f"Liga activa '{self.active_league}' no encontrada en leagues.yaml"
            )
        return self.leagues[self.active_league]

    def get_league(self, key: str) -> Optional[LeagueConfig]:
        return self.leagues.get(key)


# ── Configuración de bookmakers ───────────────────────────────────────────────

class MarketMapping(BaseModel):
    category: str
    key: str


class BookmakerConfig(BaseModel):
    """Configuración completa de una casa de apuestas (del YAML del bookmaker)."""

    bookmaker: str
    name: str
    enabled: bool = True
    market_mappings: dict[str, MarketMapping] = {}

    # Campos opcionales según la casa; se almacenan en _extra para acceso dinámico
    model_config = {"extra": "allow"}

    def get_api_field(self, *path: str, default: Any = None) -> Any:
        """Accede a campos anidados del YAML (p.ej. get_api_field('api', 'base_url'))."""
        obj = self.model_extra or {}
        for key in path:
            if not isinstance(obj, dict):
                return default
            obj = obj.get(key, default)
        return obj

    @property
    def api_base_url(self) -> str:
        return self.get_api_field("api", "base_url", default="")

    @property
    def request_delay(self) -> float:
        return float(self.get_api_field("api", "request_delay", default=0.5))

    @property
    def timeout(self) -> int:
        return int(self.get_api_field("api", "timeout", default=15))

    @property
    def extra_headers(self) -> dict[str, str]:
        return self.get_api_field("headers", default={}) or {}


# ── Cargador principal ────────────────────────────────────────────────────────

_CONFIG_ROOT = Path(os.getenv("APP_CONFIG_PATH", "config/app.yaml")).parent


class ConfigLoader:
    """
    Carga y valida todos los archivos YAML de configuración.
    Todos los métodos con @lru_cache son cacheados en memoria.
    """

    def __init__(self, config_dir: Path | None = None):
        self._dir = config_dir or _CONFIG_ROOT

    def _load_yaml(self, path: Path) -> dict:
        if not path.exists():
            raise MissingConfigError(
                f"Archivo de configuración no encontrado: {path}",
                context={"path": str(path)},
            )
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise InvalidConfigError(
                f"Error al parsear YAML: {path}",
                context={"path": str(path), "error": str(exc)},
            ) from exc
        return data

    def load_app_config(self) -> AppConfig:
        data = self._load_yaml(self._dir / "app.yaml")
        try:
            return AppConfig(**data.get("app", {}), **{
                k: v for k, v in data.items() if k != "app"
            })
        except Exception as exc:
            raise InvalidConfigError(
                "config/app.yaml inválido",
                context={"error": str(exc)},
            ) from exc

    def load_leagues(self) -> LeaguesConfig:
        data = self._load_yaml(self._dir / "leagues.yaml")
        try:
            return LeaguesConfig(**data)
        except Exception as exc:
            raise InvalidConfigError(
                "config/leagues.yaml inválido",
                context={"error": str(exc)},
            ) from exc

    def load_bookmaker(self, name: str) -> BookmakerConfig:
        path = self._dir / "bookmakers" / f"{name}.yaml"
        data = self._load_yaml(path)
        try:
            return BookmakerConfig(**data)
        except Exception as exc:
            raise InvalidConfigError(
                f"config/bookmakers/{name}.yaml inválido",
                context={"bookmaker": name, "error": str(exc)},
            ) from exc

    def load_all_bookmakers(self) -> dict[str, BookmakerConfig]:
        """Carga todos los YAML de bookmakers disponibles en config/bookmakers/."""
        bm_dir = self._dir / "bookmakers"
        if not bm_dir.exists():
            return {}
        result = {}
        for yaml_file in bm_dir.glob("*.yaml"):
            bm_key = yaml_file.stem
            result[bm_key] = self.load_bookmaker(bm_key)
        return result


# ── Singleton cacheado ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_config_loader() -> ConfigLoader:
    return ConfigLoader()


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return get_config_loader().load_app_config()


@lru_cache(maxsize=1)
def get_leagues_config() -> LeaguesConfig:
    return get_config_loader().load_leagues()


@lru_cache(maxsize=None)
def get_bookmaker_config(name: str) -> BookmakerConfig:
    return get_config_loader().load_bookmaker(name)
