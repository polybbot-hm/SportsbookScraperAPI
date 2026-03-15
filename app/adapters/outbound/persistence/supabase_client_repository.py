"""Repositorio Supabase usando supabase-py (REST API / PostgREST).

Tabla única desnormalizada: odds_raw
------------------------------------
Más simple de consultar desde Supabase y no requiere gestionar FKs.
El histórico funciona porque cada llamada inserta una nueva fila con scraped_at distinto.

SQL para crear la tabla en Supabase (ejecutar en SQL Editor):

    CREATE TABLE IF NOT EXISTS odds_raw (
        id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        external_event_id text NOT NULL,
        partido      text NOT NULL,
        home_team    text NOT NULL,
        away_team    text NOT NULL,
        liga         text NOT NULL,
        sport        text NOT NULL DEFAULT 'soccer',
        bookmaker    text NOT NULL,
        categoria    text NOT NULL,
        mercado      text NOT NULL,
        selection    text NOT NULL,
        cuota        numeric(10,4) NOT NULL,
        scraped_at   timestamptz NOT NULL DEFAULT now()
    );

    -- Índices útiles
    CREATE INDEX IF NOT EXISTS idx_odds_raw_event   ON odds_raw(external_event_id);
    CREATE INDEX IF NOT EXISTS idx_odds_raw_bm      ON odds_raw(bookmaker);
    CREATE INDEX IF NOT EXISTS idx_odds_raw_liga     ON odds_raw(liga);
    CREATE INDEX IF NOT EXISTS idx_odds_raw_scraped  ON odds_raw(scraped_at DESC);
"""

from datetime import datetime
from typing import List, Optional

from supabase import Client, create_client

from app.domain.models import BookmakerName, Event, MarketType, OddsSnapshot
from app.domain.ports.outbound.odds_repository_port import OddsRepositoryPort

TABLE = "odds_raw"


class SupabaseClientRepository(OddsRepositoryPort):
    """Repositorio usando supabase-py. Una sola tabla desnormalizada."""

    def __init__(self, supabase_url: str, supabase_key: str):
        self.client: Client = create_client(supabase_url, supabase_key)

    def _snapshot_to_row(self, s: OddsSnapshot) -> dict:
        return {
            "external_event_id": s.event.external_id,
            "partido": s.event.match_label,
            "home_team": s.event.home_team,
            "away_team": s.event.away_team,
            "liga": s.event.league_name,
            "sport": s.event.sport,
            "bookmaker": s.bookmaker.value,
            "categoria": s.market_type.value,
            "mercado": s.market_name,
            "selection": s.selection_name,
            "cuota": float(s.odds_value),
            "scraped_at": s.scraped_at.isoformat(),
        }

    def _row_to_snapshot(self, row: dict) -> OddsSnapshot:
        event = Event(
            external_id=row["external_event_id"],
            home_team=row["home_team"],
            away_team=row["away_team"],
            league_name=row["liga"],
            sport=row.get("sport", "soccer"),
        )
        try:
            bookmaker = BookmakerName(row["bookmaker"])
        except ValueError:
            bookmaker = BookmakerName.CODERE
        try:
            market_type = MarketType(row["categoria"])
        except ValueError:
            market_type = MarketType.PRINCIPALES
        return OddsSnapshot(
            event=event,
            market_name=row["mercado"],
            market_type=market_type,
            selection_name=row["selection"],
            odds_value=row["cuota"],
            bookmaker=bookmaker,
            scraped_at=datetime.fromisoformat(row["scraped_at"].replace("Z", "+00:00")),
            id=row.get("id"),
        )

    def save_snapshots(self, snapshots: List[OddsSnapshot]) -> None:
        if not snapshots:
            return
        rows = [self._snapshot_to_row(s) for s in snapshots]
        # Insertar en lotes de 500 para no exceder límites de la API
        batch = 500
        for i in range(0, len(rows), batch):
            self.client.table(TABLE).insert(rows[i : i + batch]).execute()

    def get_latest_odds(
        self,
        bookmaker: Optional[str] = None,
        league_name: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[OddsSnapshot]:
        """
        Obtiene la cuota más reciente por (event_id, bookmaker, mercado, selection).
        Supabase no soporta GROUP BY directo vía REST, así que traemos los datos
        ordenados y filtramos en Python.
        """
        q = self.client.table(TABLE).select("*").order("scraped_at", desc=True)
        if bookmaker:
            q = q.eq("bookmaker", bookmaker)
        if league_name:
            q = q.eq("liga", league_name)
        if event_id:
            q = q.eq("external_event_id", event_id)
        q = q.limit(5000)
        result = q.execute()
        rows = result.data or []

        # Dedup: solo la más reciente por (event_id, bookmaker, mercado, selection)
        seen = {}
        for row in rows:
            key = (row["external_event_id"], row["bookmaker"], row["mercado"], row["selection"])
            if key not in seen:
                seen[key] = row
        return [self._row_to_snapshot(r) for r in seen.values()]

    def get_odds_history(
        self,
        event_id: str,
        bookmaker: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[OddsSnapshot]:
        q = (
            self.client.table(TABLE)
            .select("*")
            .eq("external_event_id", event_id)
            .order("scraped_at", desc=False)
        )
        if bookmaker:
            q = q.eq("bookmaker", bookmaker)
        if from_ts:
            q = q.gte("scraped_at", from_ts.isoformat())
        if to_ts:
            q = q.lte("scraped_at", to_ts.isoformat())
        result = q.execute()
        return [self._row_to_snapshot(r) for r in (result.data or [])]

    def list_events(
        self,
        league_name: Optional[str] = None,
        bookmaker: Optional[str] = None,
    ) -> List[Event]:
        q = self.client.table(TABLE).select(
            "external_event_id, partido, home_team, away_team, liga, sport"
        ).order("scraped_at", desc=True).limit(2000)
        if league_name:
            q = q.eq("liga", league_name)
        if bookmaker:
            q = q.eq("bookmaker", bookmaker)
        result = q.execute()
        seen = set()
        events = []
        for row in (result.data or []):
            eid = row["external_event_id"]
            if eid not in seen:
                seen.add(eid)
                events.append(Event(
                    external_id=eid,
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    league_name=row["liga"],
                    sport=row.get("sport", "soccer"),
                ))
        return events

    def list_leagues_with_market(self, market_type: str = "faltas") -> List[str]:
        result = (
            self.client.table(TABLE)
            .select("liga")
            .eq("categoria", market_type)
            .execute()
        )
        return list({row["liga"] for row in (result.data or [])})

    def upsert_league_has_market(self, league_name: str, sport: str, has_market: bool) -> None:
        # En este repositorio la info se infiere de los datos; no hay tabla de ligas separada.
        pass
