"""Repositorio MongoDB: implementa OddsRepositoryPort con el nuevo modelo de EventSnapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from app.domain.exceptions import DocumentNotFoundError, SaveError
from app.domain.models.bookmaker import BookmakerName
from app.domain.models.competition import Competition
from app.domain.models.event import Event
from app.domain.models.event_snapshot import EventSnapshot
from app.domain.models.market_category import Market, MarketCategorySnapshot, Selection
from app.domain.models.odds import OddsSnapshot
from app.domain.ports.outbound.odds_repository_port import OddsRepositoryPort
from app.infrastructure.config_loader import MongoConfig

logger = structlog.get_logger(__name__)


class MongoOddsRepository(OddsRepositoryPort):
    """
    Repositorio principal basado en MongoDB.

    Colecciones:
    - odds_snapshots: un documento por evento+bookmaker scrapeado.
    - events: índice canónico de eventos normalizados (cross-bookmaker).
    """

    def __init__(self, db, cfg: MongoConfig):
        self._snapshots = db[cfg.collection_snapshots]
        self._events = db[cfg.collection_events]
        self._cfg = cfg
        self._ensure_indexes()

    # ── Índices ───────────────────────────────────────────────────────────────

    def _ensure_indexes(self) -> None:
        try:
            self._snapshots.create_index(
                [("bookmaker", 1), ("event.normalized_key", 1), ("scraped_at", -1)]
            )
            self._snapshots.create_index(
                [("event.normalized_key", 1), ("scraped_at", -1)]
            )
            self._snapshots.create_index(
                [("competition.normalized_key", 1), ("scraped_at", -1)]
            )
            self._events.create_index(
                [("normalized_key", 1)], unique=True
            )
            self._events.create_index(
                [("competition_key", 1), ("event_date", 1)]
            )
            logger.debug("mongo_indexes_ensured")
        except Exception as exc:
            logger.warning("mongo_index_error", error=str(exc))

    # ── EventSnapshot: guardar y consultar ────────────────────────────────────

    def save_event_snapshots(self, snapshots: list[EventSnapshot]) -> None:
        """Persiste EventSnapshots en MongoDB y actualiza el índice de eventos."""
        if not snapshots:
            return
        docs = [self._snapshot_to_doc(s) for s in snapshots]
        try:
            result = self._snapshots.insert_many(docs, ordered=False)
            logger.info(
                "snapshot_saved",
                count=len(result.inserted_ids),
                bookmaker=snapshots[0].bookmaker.value if snapshots else "?",
            )
        except Exception as exc:
            raise SaveError(
                f"Error al guardar snapshots en MongoDB: {exc}",
                context={"count": len(docs)},
            ) from exc

        # Actualizar índice de eventos
        for snapshot in snapshots:
            self._upsert_event_index(snapshot)

    def get_latest_event_snapshots(
        self,
        event_key: str,
        bookmakers: Optional[list[BookmakerName]] = None,
        category_keys: Optional[list[str]] = None,
    ) -> list[EventSnapshot]:
        """Último snapshot por bookmaker para el event_key dado."""
        query: dict[str, Any] = {"event.normalized_key": event_key}
        if bookmakers:
            query["bookmaker"] = {"$in": [b.value for b in bookmakers]}

        pipeline = [
            {"$match": query},
            {"$sort": {"scraped_at": -1}},
            {"$group": {
                "_id": "$bookmaker",
                "doc": {"$first": "$$ROOT"},
            }},
            {"$replaceRoot": {"newRoot": "$doc"}},
        ]

        docs = list(self._snapshots.aggregate(pipeline))

        results = []
        for doc in docs:
            try:
                snapshot = self._doc_to_snapshot(doc)
                if category_keys:
                    snapshot.market_categories = [
                        cat for cat in snapshot.market_categories
                        if cat.category_key in category_keys
                    ]
                results.append(snapshot)
            except Exception as exc:
                logger.warning("snapshot_deserialize_error", error=str(exc), doc_id=str(doc.get("_id")))

        return results

    def get_event_snapshots_history(
        self,
        event_key: str,
        bookmaker: BookmakerName,
        since: datetime,
    ) -> list[EventSnapshot]:
        """Historial de snapshots para event+bookmaker desde 'since'."""
        docs = list(
            self._snapshots.find({
                "event.normalized_key": event_key,
                "bookmaker": bookmaker.value,
                "scraped_at": {"$gte": since},
            }).sort("scraped_at", -1)
        )
        results = []
        for doc in docs:
            try:
                results.append(self._doc_to_snapshot(doc))
            except Exception as exc:
                logger.warning("snapshot_deserialize_error", error=str(exc))
        return results

    def list_events_by_competition(
        self,
        competition_key: str,
        from_date: Optional[datetime] = None,
    ) -> list[Event]:
        """Lista eventos del índice canónico."""
        query: dict[str, Any] = {"competition_key": competition_key}
        if from_date:
            query["event_date"] = {"$gte": from_date}
        docs = list(self._events.find(query).sort("event_date", 1))
        return [self._event_index_to_event(d) for d in docs]

    def get_available_categories(
        self,
        competition_key: str,
        bookmaker: Optional[BookmakerName] = None,
    ) -> dict[str, list[str]]:
        """
        Devuelve {bookmaker: [category_keys]} para la competición.
        Útil para el endpoint GET /leagues/{key}/categories.
        """
        match: dict[str, Any] = {"competition.normalized_key": competition_key}
        if bookmaker:
            match["bookmaker"] = bookmaker.value

        pipeline = [
            {"$match": match},
            {"$sort": {"scraped_at": -1}},
            {"$group": {
                "_id": "$bookmaker",
                "doc": {"$first": "$$ROOT"},
            }},
            {"$project": {
                "bookmaker": "$_id",
                "categories": "$doc.market_categories.category_key",
            }},
        ]
        docs = list(self._snapshots.aggregate(pipeline))
        return {
            d["bookmaker"]: d.get("categories", [])
            for d in docs
        }

    # ── OddsRepositoryPort legacy (para compatibilidad con CodereScraper) ─────

    def save_snapshots(self, snapshots: list[OddsSnapshot]) -> None:
        """Compatibilidad con el modelo flat legacy (Codere)."""
        if not snapshots:
            return
        docs = [
            {
                "snapshot_id":  s.id,
                "bookmaker":    s.bookmaker.value,
                "scraped_at":   s.scraped_at,
                "event": {
                    "external_id":    s.event.external_id,
                    "home_team":      s.event.home_team,
                    "away_team":      s.event.away_team,
                    "league_name":    s.event.league_name,
                    "sport":          s.event.sport,
                    "event_date":     s.event.event_date,
                    "normalized_key": s.event.normalized_key,
                },
                "market_name":    s.market_name,
                "market_type":    s.market_type.value,
                "selection_name": s.selection_name,
                "odds_value":     float(s.odds_value),
                "_schema":        "legacy_flat",
            }
            for s in snapshots
        ]
        try:
            self._snapshots.insert_many(docs, ordered=False)
        except Exception as exc:
            raise SaveError(f"Error guardando snapshots legacy: {exc}") from exc

    def get_latest_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> list[OddsSnapshot]:
        query: dict[str, Any] = {"_schema": "legacy_flat"}
        if bookmaker:
            query["bookmaker"] = bookmaker
        if league_name:
            query["event.league_name"] = league_name
        if event_id:
            query["event.external_id"] = event_id
        docs = list(self._snapshots.find(query).sort("scraped_at", -1).limit(2000))
        return [self._flat_doc_to_snapshot(d) for d in docs]

    def get_odds_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> list[OddsSnapshot]:
        query: dict[str, Any] = {"event.external_id": event_id, "_schema": "legacy_flat"}
        if bookmaker:
            query["bookmaker"] = bookmaker
        if from_ts or to_ts:
            ts_filter: dict = {}
            if from_ts:
                ts_filter["$gte"] = from_ts
            if to_ts:
                ts_filter["$lte"] = to_ts
            query["scraped_at"] = ts_filter
        docs = list(self._snapshots.find(query).sort("scraped_at", -1))
        return [self._flat_doc_to_snapshot(d) for d in docs]

    def list_events(
        self,
        league_name: Optional[str] = None,
        bookmaker: Optional[str] = None,
    ) -> list[Event]:
        query: dict[str, Any] = {}
        if league_name:
            query["competition_key"] = Competition.build_normalized_key(league_name)
        docs = list(self._events.find(query))
        return [self._event_index_to_event(d) for d in docs]

    def list_leagues_with_market(self, market_type: str = "faltas") -> list[str]:
        results = self._snapshots.distinct(
            "competition.normalized_key",
            {"market_categories.category_key": market_type},
        )
        return list(results)

    def upsert_league_has_market(self, league_name: str, sport: str, has_market: bool) -> None:
        key = Competition.build_normalized_key(league_name)
        self._events.update_many(
            {"competition_key": key},
            {"$set": {"has_market": has_market, "sport": sport}},
        )

    # ── Helpers de serialización ──────────────────────────────────────────────

    @staticmethod
    def _snapshot_to_doc(s: EventSnapshot) -> dict:
        return {
            "snapshot_id":  s.id,
            "bookmaker":    s.bookmaker.value,
            "scraped_at":   s.scraped_at,
            "competition": {
                "external_id":    s.competition.external_id,
                "name":           s.competition.name,
                "normalized_key": s.competition.normalized_key,
                "sport":          s.competition.sport,
            },
            "event": {
                "external_id":    s.event.external_id,
                "home_team":      s.event.home_team,
                "away_team":      s.event.away_team,
                "league_name":    s.event.league_name,
                "sport":          s.event.sport,
                "event_date":     s.event.event_date,
                "normalized_key": s.event.normalized_key,
            },
            "market_categories": [
                {
                    "category_key":  cat.category_key,
                    "category_name": cat.category_name,
                    "markets": [
                        {
                            "market_key":  m.market_key,
                            "market_name": m.market_name,
                            "external_id": m.external_id,
                            "line":        m.line,
                            "selections": [
                                {"key": sel.key, "name": sel.name, "odds": sel.odds}
                                for sel in m.selections
                            ],
                        }
                        for m in cat.markets
                    ],
                }
                for cat in s.market_categories
            ],
            "_schema": "event_snapshot",
        }

    @staticmethod
    def _doc_to_snapshot(doc: dict) -> EventSnapshot:
        ev_doc = doc["event"]
        event_date = ev_doc.get("event_date")
        if isinstance(event_date, str):
            event_date = datetime.fromisoformat(event_date)

        comp_doc = doc["competition"]
        competition = Competition(
            external_id=comp_doc["external_id"],
            bookmaker=BookmakerName(doc["bookmaker"]),
            name=comp_doc["name"],
            sport=comp_doc.get("sport", "football"),
            normalized_key=comp_doc["normalized_key"],
        )
        event = Event(
            external_id=ev_doc["external_id"],
            home_team=ev_doc["home_team"],
            away_team=ev_doc["away_team"],
            league_name=ev_doc.get("league_name", comp_doc["name"]),
            sport=ev_doc.get("sport", "football"),
            event_date=event_date,
        )
        categories = []
        for cat_doc in doc.get("market_categories", []):
            markets = []
            for m_doc in cat_doc.get("markets", []):
                selections = [
                    Selection(key=s["key"], name=s["name"], odds=s["odds"])
                    for s in m_doc.get("selections", [])
                ]
                markets.append(Market(
                    market_key=m_doc["market_key"],
                    market_name=m_doc["market_name"],
                    external_id=m_doc.get("external_id"),
                    line=m_doc.get("line"),
                    selections=selections,
                ))
            categories.append(MarketCategorySnapshot(
                category_key=cat_doc["category_key"],
                category_name=cat_doc["category_name"],
                markets=markets,
            ))

        return EventSnapshot(
            id=doc.get("snapshot_id", str(doc.get("_id", ""))),
            bookmaker=BookmakerName(doc["bookmaker"]),
            competition=competition,
            event=event,
            scraped_at=doc.get("scraped_at", datetime.now(timezone.utc)),
            market_categories=categories,
        )

    def _upsert_event_index(self, snapshot: EventSnapshot) -> None:
        event_key = snapshot.event.normalized_key
        bookmaker_key = snapshot.bookmaker.value

        self._events.update_one(
            {"normalized_key": event_key},
            {
                "$set": {
                    "normalized_key":    event_key,
                    "home_team":         snapshot.event.home_team,
                    "away_team":         snapshot.event.away_team,
                    "event_date":        snapshot.event.event_date,
                    "competition_key":   snapshot.competition.normalized_key,
                    "sport":             snapshot.competition.sport,
                    "last_scraped":      snapshot.scraped_at,
                },
                "$set": {f"bookmaker_refs.{bookmaker_key}": snapshot.event.external_id},
            },
            upsert=True,
        )

    @staticmethod
    def _event_index_to_event(doc: dict) -> Event:
        event_date = doc.get("event_date")
        if isinstance(event_date, str):
            event_date = datetime.fromisoformat(event_date)
        return Event(
            external_id=str(doc.get("_id", "")),
            home_team=doc.get("home_team", ""),
            away_team=doc.get("away_team", ""),
            league_name=doc.get("competition_key", ""),
            sport=doc.get("sport", "football"),
            event_date=event_date,
        )

    @staticmethod
    def _flat_doc_to_snapshot(doc: dict) -> OddsSnapshot:
        from decimal import Decimal
        from app.domain.models.market import MarketType
        ev_doc = doc.get("event", {})
        event_date = ev_doc.get("event_date")
        if isinstance(event_date, str):
            event_date = datetime.fromisoformat(event_date)
        event = Event(
            external_id=ev_doc.get("external_id", ""),
            home_team=ev_doc.get("home_team", ""),
            away_team=ev_doc.get("away_team", ""),
            league_name=ev_doc.get("league_name", ""),
            sport=ev_doc.get("sport", "football"),
            event_date=event_date,
        )
        market_type_val = doc.get("market_type", "especiales")
        try:
            market_type = MarketType(market_type_val)
        except ValueError:
            market_type = MarketType.ESPECIALES

        return OddsSnapshot(
            event=event,
            market_name=doc.get("market_name", ""),
            market_type=market_type,
            selection_name=doc.get("selection_name", ""),
            odds_value=Decimal(str(doc.get("odds_value", 0))),
            bookmaker=BookmakerName(doc.get("bookmaker", "codere")),
            scraped_at=doc.get("scraped_at", datetime.now(timezone.utc)),
            id=doc.get("snapshot_id"),
        )
