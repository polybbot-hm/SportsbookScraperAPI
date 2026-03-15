"""Scraper de Codere. Soporta múltiples categorías de mercado."""
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional, Set

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.models.market import CODERE_CATEGORY_MAP, DEFAULT_TARGET_CATEGORIES
from app.domain.ports.outbound.bookmaker_scraper_port import BookmakerScraperPort
from app.infrastructure.http_client import get_with_retry

BASE_URL = "https://m.apuestas.codere.es/NavigationService"
REFERER = "https://m.apuestas.codere.es/"

# Dentro de ESTADÍSTICAS, los que contienen "falt" son mercado de FALTAS
_FOULS_KEYWORD = "falt"


class CodereScraper(BookmakerScraperPort):
    """
    Scraper para Codere (API móvil).
    Permite scrapear categorías configurables. Por defecto usa DEFAULT_TARGET_CATEGORIES.
    """

    def __init__(self, session=None, target_categories: Optional[Set[MarketType]] = None):
        self._session = session
        self._target_categories = target_categories or DEFAULT_TARGET_CATEGORIES

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{BASE_URL}/{path}"
        r = get_with_retry(url, session=self._session, params=params, referer=REFERER)
        r.raise_for_status()
        return r.json()

    def scrape_fouls_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
    ) -> List[OddsSnapshot]:
        """Wrapper de compatibilidad: scrapea usando las categorías configuradas."""
        return self.scrape_markets(league_name=league_name, sport_handle=sport_handle)

    def scrape_markets(
        self,
        league_name: Optional[str] = None,
        sport_handle: str = "soccer",
        target_categories: Optional[Set[MarketType]] = None,
        exact_league_match: bool = False,
    ) -> List[OddsSnapshot]:
        """
        Scrapea los mercados de las categorías indicadas.
        Si target_categories es None, usa self._target_categories.
        """
        cats_to_scrape = target_categories or self._target_categories

        sports = self._get("Home/GetSports")
        sport = next((s for s in sports if s.get("SportHandle") == sport_handle), None)
        if not sport:
            return []

        countries = self._get(
            "Home/GetCountriesByDate",
            params={"sportHandle": sport_handle, "nodeId": sport["NodeId"]},
        )
        leagues = []
        for country in countries or []:
            leagues.extend(country.get("Leagues", []))

        if league_name:
            if exact_league_match:
                leagues = [l for l in leagues if l.get("Name", "").strip().lower() == league_name.strip().lower()]
            else:
                leagues = [l for l in leagues if league_name.lower() in l.get("Name", "").lower()]
        if not leagues:
            return []

        results: List[OddsSnapshot] = []
        now = datetime.utcnow()

        for league in leagues:
            league_node_id = league["NodeId"]
            events_data = self._get(
                "Event/GetMultipleEventsByDate",
                params={
                    "utcOffsetHours": 1,
                    "dayDifference": 0,
                    "parentids": league_node_id,
                    "gametypes": "1;18",
                },
            )
            events_list = (
                events_data.get(str(league_node_id), [])
                if isinstance(events_data, dict)
                else []
            )

            for ev in events_list:
                participants = ev.get("Participants", [])
                if len(participants) < 2:
                    continue
                home = (
                    participants[0]
                    .get("LocalizedNames", {})
                    .get("LocalizedValues", [{}])[0]
                    .get("Value", "Local")
                )
                away = (
                    participants[1]
                    .get("LocalizedNames", {})
                    .get("LocalizedValues", [{}])[0]
                    .get("Value", "Visitante")
                )
                event_node_id = ev.get("NodeId")

                event = Event(
                    external_id=str(event_node_id),
                    home_team=home,
                    away_team=away,
                    league_name=league.get("Name", ""),
                    sport=sport_handle,
                )

                # Obtener categorías disponibles para este evento
                cat_data = self._get(
                    "Game/GetGamesNoLiveAndCategoryInfos",
                    params={"parentid": event_node_id},
                )
                cat_list = (
                    cat_data.get("CategoriesInformation", [])
                    if isinstance(cat_data, dict)
                    else []
                )

                for cat in cat_list:
                    cat_name_raw = (cat.get("CategoryName") or "").strip()
                    # Normalizar nombre para lookup (quitar emoji y espacios extra)
                    cat_name_clean = cat_name_raw.encode("ascii", "ignore").decode().strip()
                    market_type = CODERE_CATEGORY_MAP.get(
                        cat_name_raw
                    ) or CODERE_CATEGORY_MAP.get(cat_name_clean)

                    if market_type not in cats_to_scrape:
                        continue

                    time.sleep(0.2)
                    markets_raw = self._get(
                        "Game/GetGamesNoLiveByCategoryInfo",
                        params={
                            "parentid": event_node_id,
                            "categoryInfoId": cat["CategoryId"],
                        },
                    )
                    markets_list = markets_raw if isinstance(markets_raw, list) else []

                    for mercado in markets_list:
                        market_name = mercado.get("Name", "")

                        # Si la categoría es ESTADÍSTICAS, clasificar faltas aparte
                        effective_type = market_type
                        if market_type == MarketType.ESTADISTICAS and _FOULS_KEYWORD in market_name.lower():
                            effective_type = MarketType.FALTAS

                        for result_item in mercado.get("Results", []):
                            selection = result_item.get("Name", "")
                            try:
                                odd_val = Decimal(str(result_item.get("Odd", 0)))
                            except Exception:
                                odd_val = Decimal("0")

                            results.append(
                                OddsSnapshot(
                                    event=event,
                                    market_name=market_name,
                                    market_type=effective_type,
                                    selection_name=selection,
                                    odds_value=odd_val,
                                    bookmaker=BookmakerName.CODERE,
                                    scraped_at=now,
                                )
                            )

        return results
