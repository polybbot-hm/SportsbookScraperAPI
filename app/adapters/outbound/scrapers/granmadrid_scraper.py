"""Adaptador hexagonal para Casino Gran Madrid (API Altenar + undetected-chromedriver)."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import structlog

from app.adapters.outbound.scrapers.base_scraper import BaseScraper
from app.domain.exceptions import EventsNotFoundError, ScrapingError, TokenCaptureError
from app.domain.models.bookmaker import BookmakerName
from app.domain.models.competition import Competition
from app.domain.models.event import Event
from app.domain.models.event_snapshot import EventSnapshot
from app.domain.services.market_normalizer import MarketNormalizer
from app.infrastructure.config_loader import BookmakerConfig, LeagueConfig, get_bookmaker_config
from app.infrastructure.logging_config import scraping_log_context

_BOOKMAKER = BookmakerName.GRANMADRID

# JS inyectado en la página para interceptar el token de Altenar
_INTERCEPT_JS = """
window.__altenarHeaders = [];
(function() {
    const origFetch = window.fetch;
    window.fetch = function(resource, init) {
        const url = (typeof resource === 'string') ? resource
                  : (resource && resource.url) ? resource.url : '';
        if (url.includes('sb2frontend-altenar')) {
            const h = {};
            if (init && init.headers) {
                if (init.headers instanceof Headers) {
                    for (const [k,v] of init.headers.entries()) h[k] = v;
                } else if (typeof init.headers === 'object') {
                    Object.keys(init.headers).forEach(k => h[k] = init.headers[k]);
                }
            }
            h['__url'] = url;
            window.__altenarHeaders.push(h);
        }
        return origFetch.apply(this, arguments);
    };

    const origOpen = XMLHttpRequest.prototype.open;
    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    const origSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url) {
        this.__capturedUrl = (typeof url === 'string') ? url : '';
        this.__capturedHeaders = {};
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(key, value) {
        if (this.__capturedUrl && this.__capturedUrl.includes('sb2frontend-altenar')) {
            this.__capturedHeaders[key] = value;
        }
        return origSetHeader.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function() {
        if (this.__capturedUrl && this.__capturedUrl.includes('sb2frontend-altenar')) {
            const copy = Object.assign({}, this.__capturedHeaders);
            copy['__url'] = this.__capturedUrl;
            window.__altenarHeaders.push(copy);
        }
        return origSend.apply(this, arguments);
    };
})();
"""


class GranMadridScraper(BaseScraper):
    """
    Scraper para Casino Gran Madrid (API Altenar).

    Usa undetected-chromedriver para capturar el token de autenticación que
    genera el SDK Altenar al cargar la web y luego ejecuta peticiones desde
    el propio navegador para evitar bloqueos anti-bot.
    """

    def __init__(self, bookmaker_cfg: BookmakerConfig | None = None):
        cfg = bookmaker_cfg or get_bookmaker_config("granmadrid")
        super().__init__(_BOOKMAKER, cfg)
        self._normalizer = MarketNormalizer(cfg.market_mappings, bookmaker=_BOOKMAKER.value)

    # ── Puerto principal ──────────────────────────────────────────────────────

    def scrape_event_snapshots(
        self,
        competition_key: str,
        bookmaker_cfg: BookmakerConfig,
        league_cfg: LeagueConfig,
    ) -> list[EventSnapshot]:
        bm_league = league_cfg.get_bookmaker("granmadrid")
        if not bm_league or not bm_league.champ_id:
            self._logger.warning(
                "scrape_skipped",
                reason="champ_id no configurado para esta liga",
                competition_key=competition_key,
            )
            return []

        with scraping_log_context(_BOOKMAKER.value, competition_key):
            return self._scrape(bm_league.champ_id, competition_key, league_cfg.name)

    def _scrape(
        self,
        champ_id: int,
        competition_key: str,
        league_name: str,
    ) -> list[EventSnapshot]:
        self._logger.info("scrape_started", competition_key=competition_key, champ_id=champ_id)

        with self._browser_session() as driver:
            token = self._capture_token(driver)
            if not token:
                raise TokenCaptureError(
                    "GranMadrid: no se pudo capturar el token de Altenar",
                    context={"champ_id": champ_id},
                )
            self._logger.debug("token_captured", token_prefix=token[:30])

            events_raw = self._fetch_events(driver, token, champ_id)
            if not events_raw:
                raise EventsNotFoundError(
                    f"GranMadrid: sin eventos para champ_id={champ_id}",
                    context={"champ_id": champ_id},
                )

            self._logger.info("events_fetched", count=len(events_raw["events"]))

            competition = Competition(
                external_id=str(champ_id),
                bookmaker=_BOOKMAKER,
                name=league_name,
                sport="football",
                normalized_key=competition_key,
            )

            competitors_lookup = {
                c["id"]: c["name"].strip()
                for c in events_raw.get("competitors", [])
            }

            snapshots: list[EventSnapshot] = []
            scraped_at = datetime.now(timezone.utc)

            for i, ev in enumerate(events_raw["events"], 1):
                ev_name = ev.get("name", f"evento_{ev['id']}").strip()
                self._logger.debug(
                    "event_scraping",
                    event_key=ev_name,
                    progress=f"{i}/{len(events_raw['events'])}",
                )
                try:
                    detail = self._fetch_event_detail(driver, token, ev["id"])
                    if not detail:
                        self._logger.warning("event_detail_empty", event_key=ev_name)
                        continue

                    raw_markets = self._extract_markets(detail)
                    event = self._build_event(ev, competitors_lookup, league_name)
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
                except (TokenCaptureError, EventsNotFoundError):
                    raise
                except Exception as exc:
                    self._logger.warning("event_scrape_failed", event_key=ev_name, error=str(exc))

                self._sleep()

        self._logger.info("scrape_completed", event_count=len(snapshots))
        return snapshots

    # ── Gestión del navegador ─────────────────────────────────────────────────

    @contextmanager
    def _browser_session(self):
        """Context manager que inicia y cierra el navegador automáticamente."""
        try:
            import undetected_chromedriver as uc
        except ImportError as exc:
            raise ScrapingError(
                "undetected-chromedriver no está instalado. "
                "Ejecuta: pip install undetected-chromedriver",
                context={"bookmaker": "granmadrid"},
            ) from exc

        options = uc.ChromeOptions()
        browser_cfg = self._cfg.model_extra.get("browser", {}) or {}
        if browser_cfg.get("headless", True):
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        window_size = browser_cfg.get("window_size", "1920,1080")
        options.add_argument(f"--window-size={window_size}")
        lang = browser_cfg.get("lang", "es-ES")
        options.add_argument(f"--lang={lang}")

        version_main = browser_cfg.get("version_main", None)

        self._logger.info("browser_starting")
        driver = uc.Chrome(
            options=options,
            **({"version_main": version_main} if version_main else {}),
        )
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": _INTERCEPT_JS},
        )
        try:
            yield driver
        finally:
            try:
                driver.quit()
                self._logger.debug("browser_closed")
            except Exception:
                pass

    def _capture_token(self, driver) -> str | None:
        casino_url = self._cfg.get_api_field("api", "casino_url", default="")
        wait_secs = int(self._cfg.get_api_field("api", "token_wait_seconds", default=15))

        self._logger.info("token_capture_loading", url=casino_url)
        driver.get(casino_url)
        time.sleep(wait_secs)

        captured = driver.execute_script("return window.__altenarHeaders || [];")
        for entry in captured:
            url = entry.get("__url", "")
            auth = entry.get("Authorization") or entry.get("authorization")
            if "sb2frontend-altenar" in url and auth:
                return auth
        return None

    # ── Llamadas a la API Altenar ─────────────────────────────────────────────

    def _altenar_get(self, driver, token: str, endpoint: str, extra_params: dict) -> dict | None:
        base_url = self._cfg.api_base_url
        base_params = {
            "culture":        self._cfg.get_api_field("api", "culture", default="es-ES"),
            "timezoneOffset": self._cfg.get_api_field("api", "timezone_offset", default="-60"),
            "integration":    self._cfg.get_api_field("api", "integration", default=""),
            "deviceType":     self._cfg.get_api_field("api", "device_type", default=1),
            "numFormat":      self._cfg.get_api_field("api", "num_format", default="en-GB"),
            "countryCode":    self._cfg.get_api_field("api", "country_code", default="ES"),
            **extra_params,
        }
        url = f"{base_url}/{endpoint}?{urlencode(base_params)}"
        safe_token = token.replace("'", "\\'")
        js = f"""
        var url = arguments[0];
        var callback = arguments[arguments.length - 1];
        fetch(url, {{
            method: 'GET',
            headers: {{'Authorization': '{safe_token}'}}
        }})
        .then(function(r) {{
            if (!r.ok) return r.text().then(function(t) {{
                callback(JSON.stringify({{__http_error: r.status, body: t}}));
            }});
            return r.text().then(function(t) {{ callback(t); }});
        }})
        .catch(function(e) {{
            callback(JSON.stringify({{__fetch_error: e.message}}));
        }});
        """
        delay = self._cfg.request_delay
        for attempt in range(1, 4):
            try:
                raw = driver.execute_async_script(js, url)
                if not raw:
                    self._logger.warning("altenar_empty_response", attempt=attempt)
                    time.sleep(delay)
                    continue

                data = json.loads(raw)
                if isinstance(data, dict) and "__http_error" in data:
                    self._logger.warning("altenar_http_error", status=data["__http_error"], attempt=attempt)
                    time.sleep(delay * 2)
                    continue
                if isinstance(data, dict) and "__fetch_error" in data:
                    self._logger.warning("altenar_fetch_error", error=data["__fetch_error"], attempt=attempt)
                    time.sleep(delay * 2)
                    continue
                return data

            except json.JSONDecodeError:
                self._logger.warning("altenar_json_invalid", attempt=attempt)
                time.sleep(delay)
            except Exception as exc:
                self._logger.warning("altenar_request_error", error=str(exc), attempt=attempt)
                time.sleep(delay)

        return None

    def _fetch_events(self, driver, token: str, champ_id: int) -> dict | None:
        return self._altenar_get(driver, token, "GetEvents", {
            "eventCount": "0",
            "sportId":    "0",
            "champIds":   str(champ_id),
        })

    def _fetch_event_detail(self, driver, token: str, event_id: int) -> dict | None:
        return self._altenar_get(driver, token, "GetEventDetails", {
            "eventId":       str(event_id),
            "showNonBoosts": "false",
        })

    # ── Parsing ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_markets(detail: dict) -> list[dict]:
        odds_lookup = {o["id"]: o for o in detail.get("odds", [])}
        result = []
        for market in detail.get("markets", []):
            odd_ids = [
                oid
                for sublist in market.get("desktopOddIds", [])
                for oid in sublist
            ]
            cuotas = [
                {"nombre": odds_lookup[oid]["name"], "cuota": odds_lookup[oid]["price"]}
                for oid in odd_ids
                if oid in odds_lookup
            ]
            entry: dict[str, Any] = {
                "market_id":      market["id"],
                "market_type_id": market.get("typeId"),
                "nombre_mercado": market.get("name", ""),
                "cuotas":         cuotas,
            }
            if market.get("sv"):
                sv_raw = market["sv"].split("|")[0]
                try:
                    entry["linea"] = float(sv_raw)
                except ValueError:
                    pass
            result.append(entry)
        return result

    @staticmethod
    def _build_event(
        raw: dict,
        competitors_lookup: dict[int, str],
        league_name: str,
    ) -> Event:
        comp_ids = raw.get("competitorIds", [])
        home = competitors_lookup.get(comp_ids[0], "Local") if len(comp_ids) > 0 else "Local"
        away = competitors_lookup.get(comp_ids[1], "Visitante") if len(comp_ids) > 1 else "Visitante"

        start_str = raw.get("startDate", "")
        event_date: datetime | None = None
        if start_str:
            try:
                event_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return Event(
            external_id=str(raw["id"]),
            home_team=home,
            away_team=away,
            league_name=league_name,
            sport="football",
            event_date=event_date,
        )
