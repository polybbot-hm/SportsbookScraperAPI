"""Modelos SQLAlchemy para persistencia (Supabase/PostgreSQL, compatibles con SQLite para tests)."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def gen_uuid():
    return str(uuid4())


class BookmakerModel(Base):
    __tablename__ = "bookmakers"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(64), unique=True, nullable=False)
    slug = Column(String(64), unique=True, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeagueModel(Base):
    __tablename__ = "leagues"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    sport = Column(String(64), nullable=False)
    has_fouls_market = Column(Boolean, default=False)
    metadata_ = Column(Text, nullable=True)  # JSON string para compat SQLite
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EventModel(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    external_id = Column(String(128), nullable=False, index=True)
    league_id = Column(String(36), ForeignKey("leagues.id"), nullable=True)
    home_team = Column(String(255), nullable=False)
    away_team = Column(String(255), nullable=False)
    event_date = Column(DateTime, nullable=True)
    status = Column(String(32), default="upcoming")
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketModel(Base):
    __tablename__ = "markets"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    event_id = Column(String(36), ForeignKey("events.id"), nullable=False)
    name = Column(String(255), nullable=False)
    market_type = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OddsSnapshotModel(Base):
    __tablename__ = "odds_snapshots"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    market_id = Column(String(36), ForeignKey("markets.id"), nullable=False)
    bookmaker_id = Column(String(36), ForeignKey("bookmakers.id"), nullable=False)
    selection_name = Column(String(255), nullable=False)
    odds_value = Column(Numeric(10, 4), nullable=False)
    scraped_at = Column(DateTime, nullable=False)
