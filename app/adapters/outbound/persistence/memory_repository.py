"""Repositorio en memoria (sin DB). Útil cuando no hay DATABASE_URL."""
from datetime import datetime
from typing import List, Optional

from app.domain.models import Event, OddsSnapshot
from app.domain.ports.outbound.odds_repository_port import OddsRepositoryPort


class InMemoryOddsRepository(OddsRepositoryPort):
    """Implementación en memoria para desarrollo o cuando no hay base de datos."""

    def __init__(self):
        self._snapshots: List[OddsSnapshot] = []
        self._leagues_with_market: List[str] = []

    def save_snapshots(self, snapshots: List[OddsSnapshot]) -> None:
        self._snapshots.extend(snapshots)

    def get_latest_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        out = list(self._snapshots)
        if bookmaker:
            out = [s for s in out if s.bookmaker.value == bookmaker]
        if league_name:
            out = [s for s in out if s.event.league_name == league_name]
        if event_id:
            out = [s for s in out if s.event.external_id == event_id]
        # Último por (event, market, bookmaker, selection)
        seen = {}
        for s in sorted(out, key=lambda x: x.scraped_at, reverse=True):
            key = (s.event.external_id, s.market_name, s.bookmaker.value, s.selection_name)
            if key not in seen:
                seen[key] = s
        return list(seen.values())

    def get_odds_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[OddsSnapshot]:
        out = [s for s in self._snapshots if s.event.external_id == event_id]
        if bookmaker:
            out = [s for s in out if s.bookmaker.value == bookmaker]
        if from_ts:
            out = [s for s in out if s.scraped_at >= from_ts]
        if to_ts:
            out = [s for s in out if s.scraped_at <= to_ts]
        return sorted(out, key=lambda s: s.scraped_at)

    def list_events(
        self,
        league_name: Optional[str] = None,
        bookmaker: Optional[str] = None,
    ) -> List[Event]:
        out = self._snapshots
        if league_name:
            out = [s for s in out if s.event.league_name == league_name]
        if bookmaker:
            out = [s for s in out if s.bookmaker.value == bookmaker]
        seen = set()
        result = []
        for s in out:
            if s.event.external_id not in seen:
                seen.add(s.event.external_id)
                result.append(s.event)
        return result

    def list_leagues_with_market(self, market_type: str = "faltas") -> List[str]:
        return list(self._leagues_with_market)

    def upsert_league_has_market(self, league_name: str, sport: str, has_market: bool) -> None:
        if has_market and league_name not in self._leagues_with_market:
            self._leagues_with_market.append(league_name)
