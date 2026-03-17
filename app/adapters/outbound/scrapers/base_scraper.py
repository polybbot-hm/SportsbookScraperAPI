"""Clase base compartida por todos los scrapers de la arquitectura hexagonal."""
from __future__ import annotations

import random
import time
from typing import Any, Optional

import requests
import structlog
from requests import Response, Session

from app.domain.exceptions import HttpRequestError, ScrapingError
from app.domain.models.bookmaker import BookmakerName
from app.domain.models.market_category import MarketCategorySnapshot
from app.domain.ports.outbound.bookmaker_scraper_port import BookmakerScraperPort
from app.infrastructure.config_loader import BookmakerConfig, LeagueConfig


class BaseScraper(BookmakerScraperPort):
    """
    Clase base para scrapers hexagonales.

    Proporciona:
    - HTTP GET con retry exponencial y logging estructurado.
    - Delays aleatorios entre peticiones.
    - Método scrape_event_snapshots() para los nuevos scrapers.
    - Implementación vacía de scrape_markets() para compatibilidad con el puerto legacy.
    """

    def __init__(
        self,
        bookmaker: BookmakerName,
        bookmaker_cfg: BookmakerConfig,
        session: Optional[Session] = None,
    ):
        self._bookmaker = bookmaker
        self._cfg = bookmaker_cfg
        self._session = session or requests.Session()
        self._logger = structlog.get_logger(self.__class__.__name__).bind(
            bookmaker=bookmaker.value
        )

        # Configurar headers por defecto desde el YAML
        headers = bookmaker_cfg.extra_headers
        if headers:
            self._session.headers.update(headers)

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> Response:
        """GET con retry exponencial según la configuración del bookmaker."""
        max_attempts = self._cfg.get_api_field(
            "api", "retry", default={}
        )
        retry_cfg = self._cfg.model_extra.get("retry") if self._cfg.model_extra else {}
        max_attempts = int((retry_cfg or {}).get("max_attempts", 3))
        wait_min = float((retry_cfg or {}).get("wait_min", 1.0))
        wait_max = float((retry_cfg or {}).get("wait_max", 5.0))
        timeout = timeout or self._cfg.timeout

        last_exc: Exception = RuntimeError("Sin intentos")
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                resp.raise_for_status()
                self._logger.debug(
                    "http_get_ok",
                    url=url,
                    status=resp.status_code,
                    attempt=attempt,
                )
                return resp

            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                self._logger.warning(
                    "http_error",
                    url=url,
                    status=status,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                last_exc = HttpRequestError(
                    f"HTTP {status} en {url}",
                    status_code=status,
                    context={"url": url, "attempt": attempt},
                )
                if status and 400 <= status < 500:
                    # Error del cliente: no reintentar
                    raise last_exc from exc

            except requests.RequestException as exc:
                self._logger.warning(
                    "request_exception",
                    url=url,
                    error=str(exc),
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                last_exc = ScrapingError(
                    f"Error de red en {url}: {exc}",
                    context={"url": url, "attempt": attempt},
                )

            if attempt < max_attempts:
                wait = random.uniform(wait_min, wait_max)
                time.sleep(wait)

        raise last_exc

    def _sleep(self, extra: float = 0.0) -> None:
        """Pausa aleatoria según el delay configurado para el bookmaker."""
        delay = self._cfg.request_delay + extra
        jitter = random.uniform(0, delay * 0.2)
        time.sleep(delay + jitter)

    # ── Puerto legacy (compatibilidad) ────────────────────────────────────────

    def scrape_markets(self, **kwargs) -> list:
        """
        Implementación de compatibilidad con BookmakerScraperPort legacy.
        Los nuevos scrapers implementan scrape_event_snapshots() en su lugar.
        """
        return []

    # ── Nuevo puerto ─────────────────────────────────────────────────────────

    def scrape_event_snapshots(
        self,
        competition_key: str,
        bookmaker_cfg: BookmakerConfig,
        league_cfg: LeagueConfig,
    ):
        """
        Punto de entrada principal para los nuevos scrapers.
        Debe ser sobreescrito por cada subclase.

        Returns:
            list[EventSnapshot]
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} debe implementar scrape_event_snapshots()"
        )
