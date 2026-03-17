"""Adaptador hexagonal para SpeedyBet (API Kambi)."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.adapters.outbound.scrapers.base_scraper import BaseScraper
from app.domain.exceptions import EventsNotFoundError, ScrapingError
from app.domain.models.bookmaker import BookmakerName
from app.domain.models.competition import Competition
from app.domain.models.event import Event
from app.domain.models.event_snapshot import EventSnapshot
from app.domain.services.market_normalizer import MarketNormalizer
from app.infrastructure.config_loader import BookmakerConfig, LeagueConfig, get_bookmaker_config
from app.infrastructure.logging_config import scraping_log_context

_BOOKMAKER = BookmakerName.SPEEDY


class SpeedyScraper(BaseScraper):
    """
    Scraper para SpeedyBet usando la API pública de Kambi.
    Implementa la arquitectura hexagonal a través de BaseScraper.
    """

    def __init__(self, bookmaker_cfg: BookmakerConfig | None = None):
        cfg = bookmaker_cfg or get_bookmaker_config("speedy")
        super().__init__(_BOOKMAKER, cfg)
        self._normalizer = MarketNormalizer(cfg.market_mappings, bookmaker=_BOOKMAKER.value)

    # ── Puerto principal ──────────────────────────────────────────────────────

    def scrape_event_snapshots(
        self,
        competition_key: str,
        bookmaker_cfg: BookmakerConfig,
        league_cfg: LeagueConfig,
    ) -> list[EventSnapshot]:
        """Scrapea todos los eventos y mercados de la competición."""
        bm_league = league_cfg.get_bookmaker("speedy")
        if not bm_league or not bm_league.group_id:
            self._logger.warning(
                "scrape_skipped",
                reason="group_id no configurado para esta liga",
                competition_key=competition_key,
            )
            return []

        with scraping_log_context(_BOOKMAKER.value, competition_key):
            return self._scrape(bm_league.group_id, competition_key, league_cfg.name)

    def _scrape(
        self,
        group_id: int,
        competition_key: str,
        league_name: str,
    ) -> list[EventSnapshot]:
        self._logger.info(
            "scrape_started",
            competition_key=competition_key,
            group_id=group_id,
        )

        events_raw = self._fetch_events(group_id)
        if not events_raw:
            raise EventsNotFoundError(
                f"SpeedyBet: no se encontraron eventos para group_id={group_id}",
                context={"group_id": group_id, "competition_key": competition_key},
            )

        self._logger.info("events_fetched", count=len(events_raw))

        competition = Competition(
            external_id=str(group_id),
            bookmaker=_BOOKMAKER,
            name=league_name,
            sport="football",
            normalized_key=competition_key,
        )

        snapshots: list[EventSnapshot] = []
        scraped_at = datetime.now(timezone.utc)

        for i, ev_raw in enumerate(events_raw, 1):
            event_id = str(ev_raw["id"])
            event_name = ev_raw.get("name", f"evento_{event_id}")
            self._logger.debug(
                "event_scraping",
                event_key=event_name,
                progress=f"{i}/{len(events_raw)}",
            )

            try:
                raw_markets = self._fetch_markets(ev_raw["id"])
                event = self._build_event(ev_raw, competition_key, league_name)
                categories = self._normalizer.normalize(raw_markets)

                snapshot = EventSnapshot(
                    bookmaker=_BOOKMAKER,
                    competition=competition,
                    event=event,
                    scraped_at=scraped_at,
                    market_categories=categories,
                )
                snapshots.append(snapshot)

                self._logger.debug(
                    "event_scraped",
                    event_key=event.normalized_key,
                    market_count=snapshot.total_markets,
                )
            except ScrapingError:
                raise
            except Exception as exc:
                self._logger.warning(
                    "event_scrape_failed",
                    event_key=event_name,
                    error=str(exc),
                )

            self._sleep()

        self._logger.info(
            "scrape_completed",
            event_count=len(snapshots),
        )
        return snapshots

    # ── Llamadas a la API Kambi ───────────────────────────────────────────────

    def _fetch_events(self, group_id: int) -> list[dict]:
        base_url = self._cfg.api_base_url
        params = {
            "lang":       self._cfg.get_api_field("api", "lang", default="es_ES"),
            "market":     self._cfg.get_api_field("api", "market", default="ES"),
            "client_id":  self._cfg.get_api_field("api", "client_id", default=200),
            "channel_id": self._cfg.get_api_field("api", "channel_id", default=1),
        }
        resp = self._get(f"{base_url}/event/group/{group_id}.json", params=params)
        events = resp.json().get("events", [])
        events.sort(key=lambda x: x.get("start", ""))
        return events

    def _fetch_markets(self, event_id: int) -> list[dict]:
        base_url = self._cfg.api_base_url
        params = {
            "lang":           self._cfg.get_api_field("api", "lang", default="es_ES"),
            "market":         self._cfg.get_api_field("api", "market", default="ES"),
            "client_id":      self._cfg.get_api_field("api", "client_id", default=200),
            "channel_id":     self._cfg.get_api_field("api", "channel_id", default=1),
            "include":        "all",
            "categoryGroup":  "COMBINED",
            "displayDefault": "true",
        }
        resp = self._get(f"{base_url}/betoffer/event/{event_id}.json", params=params)
        raw_offers = resp.json().get("betOffers", [])
        return [self._normalize_raw_market(offer, idx) for idx, offer in enumerate(raw_offers)]

    @staticmethod
    def _normalize_raw_market(offer: dict, idx: int) -> dict:
        """Convierte un betOffer de Kambi al formato raw estándar del dominio."""
        criterion = offer.get("criterion", {})
        cuotas = []
        for outcome in offer.get("outcomes", []):
            if "odds" not in outcome:
                continue
            entry: dict = {
                "nombre": outcome.get("label", ""),
                "cuota":  round(outcome["odds"] / 1000, 4),
            }
            if outcome.get("line") is not None:
                entry["linea"] = outcome["line"] / 1000
            cuotas.append(entry)

        result: dict = {
            "market_id":      offer.get("id", idx),
            "market_type_id": criterion.get("id"),
            "nombre_mercado": criterion.get("label", ""),
            "cuotas":         cuotas,
        }
        lines = {c["linea"] for c in cuotas if "linea" in c}
        if len(lines) == 1:
            result["linea"] = lines.pop()

        return result

    @staticmethod
    def _build_event(raw: dict, competition_key: str, league_name: str) -> Event:
        """Construye un Event de dominio a partir del raw de Kambi."""
        start_str = raw.get("start", "")
        event_date: datetime | None = None
        if start_str:
            try:
                event_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return Event(
            external_id=str(raw["id"]),
            home_team=raw.get("homeName", raw.get("name", "Local")),
            away_team=raw.get("awayName", "Visitante"),
            league_name=league_name,
            sport="football",
            event_date=event_date,
        )
