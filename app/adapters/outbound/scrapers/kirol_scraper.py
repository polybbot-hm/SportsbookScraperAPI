"""Adaptador hexagonal para Kirolbet (HTML scraping con BeautifulSoup)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.adapters.outbound.scrapers.base_scraper import BaseScraper
from app.domain.exceptions import EventsNotFoundError, MarketParseError
from app.domain.models.bookmaker import BookmakerName
from app.domain.models.competition import Competition
from app.domain.models.event import Event
from app.domain.models.event_snapshot import EventSnapshot
from app.domain.services.market_normalizer import MarketNormalizer
from app.infrastructure.config_loader import BookmakerConfig, LeagueConfig, get_bookmaker_config
from app.infrastructure.logging_config import scraping_log_context

_BOOKMAKER = BookmakerName.KIROL


class KirolScraper(BaseScraper):
    """
    Scraper para Kirolbet.
    Parsea HTML con BeautifulSoup para extraer eventos y cuotas.
    """

    def __init__(self, bookmaker_cfg: BookmakerConfig | None = None):
        cfg = bookmaker_cfg or get_bookmaker_config("kirol")
        super().__init__(_BOOKMAKER, cfg)
        self._normalizer = MarketNormalizer(cfg.market_mappings, bookmaker=_BOOKMAKER.value)

    # ── Puerto principal ──────────────────────────────────────────────────────

    def scrape_event_snapshots(
        self,
        competition_key: str,
        bookmaker_cfg: BookmakerConfig,
        league_cfg: LeagueConfig,
    ) -> list[EventSnapshot]:
        bm_league = league_cfg.get_bookmaker("kirol")
        if not bm_league or not bm_league.competition_id:
            self._logger.warning(
                "scrape_skipped",
                reason="competition_id no configurado para esta liga",
                competition_key=competition_key,
            )
            return []

        with scraping_log_context(_BOOKMAKER.value, competition_key):
            return self._scrape(bm_league.competition_id, competition_key, league_cfg.name)

    def _scrape(
        self,
        competition_id: int,
        competition_key: str,
        league_name: str,
    ) -> list[EventSnapshot]:
        self._logger.info(
            "scrape_started",
            competition_key=competition_key,
            competition_id=competition_id,
        )

        events_list = self._fetch_event_list(competition_id)
        if not events_list:
            raise EventsNotFoundError(
                f"Kirolbet: sin eventos para competition_id={competition_id}",
                context={"competition_id": competition_id},
            )

        self._logger.info("events_fetched", count=len(events_list))

        competition = Competition(
            external_id=str(competition_id),
            bookmaker=_BOOKMAKER,
            name=league_name,
            sport="football",
            normalized_key=competition_key,
        )

        snapshots: list[EventSnapshot] = []
        scraped_at = datetime.now(timezone.utc)

        for i, ev_stub in enumerate(events_list, 1):
            ev_name = ev_stub.get("nombre", ev_stub["id"])
            self._logger.debug(
                "event_scraping",
                event_key=ev_name,
                progress=f"{i}/{len(events_list)}",
            )
            try:
                ev_data = self._scrape_event_page(ev_stub)
                event = self._build_event(ev_data, league_name)
                categories = self._normalizer.normalize(ev_data["mercados"])

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
            except (EventsNotFoundError,):
                raise
            except Exception as exc:
                self._logger.warning("event_scrape_failed", event_key=ev_name, error=str(exc))

            self._sleep()

        self._logger.info("scrape_completed", event_count=len(snapshots))
        return snapshots

    # ── Parseo HTML ───────────────────────────────────────────────────────────

    def _get_soup(self, url: str):
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise MarketParseError(
                "beautifulsoup4 no está instalado. Ejecuta: pip install beautifulsoup4 lxml",
                context={"bookmaker": "kirol"},
            ) from exc

        resp = self._get(url)
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "html.parser")

    def _fetch_event_list(self, competition_id: int) -> list[dict]:
        base_url = self._cfg.get_api_field("web", "base_url", default="https://apuestas.kirolbet.es")
        url = f"{base_url}/esp/Sport/Competicion/{competition_id}"
        soup = self._get_soup(url)

        seen, events = set(), []
        for a in soup.find_all("a", href=re.compile(r"/esp/Sport/Evento/\d+")):
            m = re.search(r"/Evento/(\d+)", a["href"])
            if not m:
                continue
            event_id = m.group(1)
            if event_id in seen:
                continue

            name = re.sub(r"\(\+\s*\d+\)", "", a.get_text(strip=True)).strip()
            if not name or len(name) < 3:
                continue

            seen.add(event_id)
            events.append({
                "id":     event_id,
                "nombre": name,
                "url":    f"{base_url}/esp/Sport/Evento/{event_id}",
            })

        return events

    def _scrape_event_page(self, ev_stub: dict) -> dict:
        soup = self._get_soup(ev_stub["url"])

        # Intentar extraer fecha del HTML
        fecha: Optional[str] = None
        time_span = soup.find("span", class_=re.compile(r"fecha|date|time", re.I))
        if time_span:
            fecha = time_span.get_text(strip=True)

        nombre = ev_stub["nombre"]
        partes = re.split(r"\s+vs\.?\s+", nombre, flags=re.I)
        local     = partes[0].strip() if len(partes) > 0 else "?"
        visitante = partes[1].strip() if len(partes) > 1 else "?"

        mercados = []
        for idx, market_el in enumerate(soup.find_all("ul", class_=re.compile(r"marketGroup"))):
            title_li = market_el.find("li")
            if not title_li:
                continue
            nombre_mercado = re.sub(r"\s+", " ", title_li.get_text(strip=True))
            if not nombre_mercado:
                continue

            cuotas = []
            for anchor in market_el.find_all("a", class_=re.compile(r"it_\d+")):
                label_span = anchor.find("span", class_="pron")
                coef_span  = anchor.find("span", class_="coef")
                if not label_span or not coef_span:
                    continue
                raw = coef_span.get_text(strip=True).replace(",", ".")
                try:
                    cuota_val = float(raw)
                except ValueError:
                    cuota_val = raw
                cuotas.append({
                    "nombre": label_span.get_text(strip=True),
                    "cuota":  cuota_val,
                })

            entry: dict = {
                "market_id":      idx,
                "nombre_mercado": nombre_mercado,
                "cuotas":         cuotas,
            }

            # Intentar extraer línea del nombre del mercado
            linea_match = re.search(r"[\+\-]?\d+(?:[.,]\d+)?", nombre_mercado)
            if linea_match and any(c in nombre_mercado for c in ["+", "-", "Más", "Menos", "Total"]):
                raw_linea = linea_match.group().replace(",", ".")
                try:
                    entry["linea"] = float(raw_linea)
                except ValueError:
                    pass

            mercados.append(entry)

        return {
            "event_id":  ev_stub["id"],
            "partido":   nombre,
            "local":     local,
            "visitante": visitante,
            "fecha":     fecha,
            "mercados":  mercados,
        }

    @staticmethod
    def _build_event(data: dict, league_name: str) -> Event:
        fecha_str = data.get("fecha")
        event_date: Optional[datetime] = None
        if fecha_str:
            for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y"):
                try:
                    event_date = datetime.strptime(fecha_str, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

        return Event(
            external_id=str(data["event_id"]),
            home_team=data.get("local", "Local"),
            away_team=data.get("visitante", "Visitante"),
            league_name=league_name,
            sport="football",
            event_date=event_date,
        )
