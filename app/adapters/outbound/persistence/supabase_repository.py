"""Repositorio de odds usando SQLAlchemy (Supabase/PostgreSQL o SQLite)."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.ports.outbound.odds_repository_port import OddsRepositoryPort
from app.adapters.outbound.persistence.db_models import (
    Base,
    BookmakerModel,
    LeagueModel,
    EventModel,
    MarketModel,
    OddsSnapshotModel,
)


class SupabaseRepository(OddsRepositoryPort):
    """Implementación del repositorio con SQLAlchemy."""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def _session(self) -> Session:
        return self._session_factory()

    def _get_or_create_bookmaker(self, session: Session, name: str, slug: str) -> str:
        row = session.query(BookmakerModel).filter(BookmakerModel.slug == slug).first()
        if row:
            return row.id
        row = BookmakerModel(name=name, slug=slug)
        session.add(row)
        session.flush()
        return row.id

    def _get_or_create_league(self, session: Session, name: str, sport: str) -> str:
        row = session.query(LeagueModel).filter(
            LeagueModel.name == name,
            LeagueModel.sport == sport,
        ).first()
        if row:
            return row.id
        row = LeagueModel(name=name, sport=sport)
        session.add(row)
        session.flush()
        return row.id

    def _get_or_create_event(
        self,
        session: Session,
        external_id: str,
        league_id: str,
        home_team: str,
        away_team: str,
        event_date: Optional[datetime] = None,
    ) -> str:
        row = session.query(EventModel).filter(EventModel.external_id == external_id).first()
        if row:
            return row.id
        row = EventModel(
            external_id=external_id,
            league_id=league_id,
            home_team=home_team,
            away_team=away_team,
            event_date=event_date,
        )
        session.add(row)
        session.flush()
        return row.id

    def _get_or_create_market(
        self,
        session: Session,
        event_id: str,
        name: str,
        market_type: str,
    ) -> str:
        row = session.query(MarketModel).filter(
            MarketModel.event_id == event_id,
            MarketModel.name == name,
        ).first()
        if row:
            return row.id
        row = MarketModel(event_id=event_id, name=name, market_type=market_type)
        session.add(row)
        session.flush()
        return row.id

    def save_snapshots(self, snapshots: List[OddsSnapshot]) -> None:
        if not snapshots:
            return
        with self._session() as session:
            try:
                for s in snapshots:
                    bm_id = self._get_or_create_bookmaker(
                        session, s.bookmaker.value, s.bookmaker.value
                    )
                    league_id = self._get_or_create_league(
                        session, s.event.league_name, s.event.sport
                    )
                    event_id = self._get_or_create_event(
                        session,
                        s.event.external_id,
                        league_id,
                        s.event.home_team,
                        s.event.away_team,
                        s.event.event_date,
                    )
                    market_id = self._get_or_create_market(
                        session,
                        event_id,
                        s.market_name,
                        s.market_type.value,
                    )
                    snap = OddsSnapshotModel(
                        market_id=market_id,
                        bookmaker_id=bm_id,
                        selection_name=s.selection_name,
                        odds_value=s.odds_value,
                        scraped_at=s.scraped_at,
                    )
                    session.add(snap)
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_latest_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        with self._session() as session:
            q = (
                session.query(OddsSnapshotModel, EventModel, LeagueModel, BookmakerModel, MarketModel)
                .join(MarketModel, OddsSnapshotModel.market_id == MarketModel.id)
                .join(EventModel, MarketModel.event_id == EventModel.id)
                .join(LeagueModel, EventModel.league_id == LeagueModel.id)
                .join(BookmakerModel, OddsSnapshotModel.bookmaker_id == BookmakerModel.id)
            )
            if event_id:
                q = q.filter(EventModel.external_id == event_id)
            if league_name:
                q = q.filter(LeagueModel.name == league_name)
            if bookmaker:
                q = q.filter(BookmakerModel.slug == bookmaker)

            subq = (
                session.query(
                    OddsSnapshotModel.market_id,
                    OddsSnapshotModel.bookmaker_id,
                    OddsSnapshotModel.selection_name,
                    func.max(OddsSnapshotModel.scraped_at).label("max_ts"),
                )
                .group_by(
                    OddsSnapshotModel.market_id,
                    OddsSnapshotModel.bookmaker_id,
                    OddsSnapshotModel.selection_name,
                )
            ).subquery()

            # Latest snapshot per (market, bookmaker, selection)
            q = q.join(
                subq,
                and_(
                    OddsSnapshotModel.market_id == subq.c.market_id,
                    OddsSnapshotModel.bookmaker_id == subq.c.bookmaker_id,
                    OddsSnapshotModel.selection_name == subq.c.selection_name,
                    OddsSnapshotModel.scraped_at == subq.c.max_ts,
                ),
            )
            rows = q.all()
            result = []
            for snap, event, league, bm, market in rows:
                s = OddsSnapshot(
                    event=Event(
                        external_id=event.external_id,
                        home_team=event.home_team,
                        away_team=event.away_team,
                        league_name=league.name,
                        sport=league.sport,
                        event_date=event.event_date,
                    ),
                    market_name=market.name,
                    market_type=MarketType.FALTAS,
                    selection_name=snap.selection_name,
                    odds_value=snap.odds_value,
                    bookmaker=BookmakerName(bm.slug),
                    scraped_at=snap.scraped_at,
                    id=snap.id,
                    event_id=event.id,
                    market_id=snap.market_id,
                )
                result.append(s)
            return result

    def get_odds_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[OddsSnapshot]:
        with self._session() as session:
            q = (
                session.query(OddsSnapshotModel, EventModel, LeagueModel, BookmakerModel, MarketModel)
                .join(MarketModel, OddsSnapshotModel.market_id == MarketModel.id)
                .join(EventModel, MarketModel.event_id == EventModel.id)
                .join(LeagueModel, EventModel.league_id == LeagueModel.id)
                .join(BookmakerModel, OddsSnapshotModel.bookmaker_id == BookmakerModel.id)
                .filter(EventModel.external_id == event_id)
            )
            if bookmaker:
                q = q.filter(BookmakerModel.slug == bookmaker)
            if from_ts:
                q = q.filter(OddsSnapshotModel.scraped_at >= from_ts)
            if to_ts:
                q = q.filter(OddsSnapshotModel.scraped_at <= to_ts)
            q = q.order_by(OddsSnapshotModel.scraped_at)
            rows = q.all()
            result = []
            for snap, event, league, bm, market in rows:
                result.append(
                    OddsSnapshot(
                        event=Event(
                            external_id=event.external_id,
                            home_team=event.home_team,
                            away_team=event.away_team,
                            league_name=league.name,
                            sport=league.sport,
                            event_date=event.event_date,
                        ),
                        market_name=market.name,
                        market_type=MarketType.FALTAS,
                        selection_name=snap.selection_name,
                        odds_value=snap.odds_value,
                        bookmaker=BookmakerName(bm.slug),
                        scraped_at=snap.scraped_at,
                        id=snap.id,
                        event_id=event.id,
                        market_id=snap.market_id,
                    )
                )
            return result

    def list_events(
        self,
        league_name: Optional[str] = None,
        bookmaker: Optional[str] = None,
    ) -> List[Event]:
        with self._session() as session:
            q = (
                session.query(EventModel, LeagueModel)
                .join(LeagueModel, EventModel.league_id == LeagueModel.id)
            )
            if league_name:
                q = q.filter(LeagueModel.name == league_name)
            if bookmaker:
                q = (
                    q.join(MarketModel, MarketModel.event_id == EventModel.id)
                    .join(OddsSnapshotModel, OddsSnapshotModel.market_id == MarketModel.id)
                    .join(BookmakerModel, OddsSnapshotModel.bookmaker_id == BookmakerModel.id)
                    .filter(BookmakerModel.slug == bookmaker)
                )
            q = q.distinct()
            rows = q.all()
            return [
                Event(
                    external_id=e.external_id,
                    home_team=e.home_team,
                    away_team=e.away_team,
                    league_name=league.name,
                    sport=league.sport,
                    event_date=e.event_date,
                )
                for e, league in rows
            ]

    def list_leagues_with_market(self, market_type: str = "faltas") -> List[str]:
        with self._session() as session:
            rows = session.query(LeagueModel.name).filter(LeagueModel.has_fouls_market == True).all()
            return [r[0] for r in rows]

    def upsert_league_has_market(self, league_name: str, sport: str, has_market: bool) -> None:
        with self._session() as session:
            row = session.query(LeagueModel).filter(
                LeagueModel.name == league_name,
                LeagueModel.sport == sport,
            ).first()
            if row:
                row.has_fouls_market = has_market
            else:
                session.add(LeagueModel(name=league_name, sport=sport, has_fouls_market=has_market))
            session.commit()
