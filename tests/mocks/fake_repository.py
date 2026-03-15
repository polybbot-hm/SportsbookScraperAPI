"""Repositorio falso para tests."""
from datetime import datetime
from typing import List, Optional

from app.domain.models import Event, OddsSnapshot
from app.domain.ports.outbound.odds_repository_port import OddsRepositoryPort


class FakeOddsRepository(OddsRepositoryPort):
    def __init__(self):
        self.snapshots: List[OddsSnapshot] = []
        self.leagues_with_market: List[str] = []
        self.league_has_market: dict = {}

    def save_snapshots(self, snapshots: List[OddsSnapshot]) -> None:
        self.snapshots.extend(snapshots)

    def get_latest_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        out = list(self.snapshots)
        if bookmaker:
            out = [s for s in out if s.bookmaker.value == bookmaker]
        if league_name:
            out = [s for s in out if s.event.league_name == league_name]
        if event_id:
            out = [s for s in out if s.event.external_id == event_id]
        return out

    def get_odds_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[OddsSnapshot]:
        out = [s for s in self.snapshots if s.event.external_id == event_id]
        if bookmaker:
            out = [s for s in out if s.bookmaker.value == bookmaker]
        return sorted(out, key=lambda s: s.scraped_at)

    def list_events(
        self,
        league_name: Optional[str] = None,
        bookmaker: Optional[str] = None,
    ) -> List[Event]:
        events_seen = set()
        result = []
        for s in self.snapshots:
            if league_name and s.event.league_name != league_name:
                continue
            if bookmaker and s.bookmaker.value != bookmaker:
                continue
            key = s.event.external_id
            if key not in events_seen:
                events_seen.add(key)
                result.append(s.event)
        return result

    def list_leagues_with_market(self, market_type: str = "faltas") -> List[str]:
        return list(self.leagues_with_market)

    def upsert_league_has_market(self, league_name: str, sport: str, has_market: bool) -> None:
        self.league_has_market[(league_name, sport)] = has_market
        if has_market and league_name not in self.leagues_with_market:
            self.leagues_with_market.append(league_name)
