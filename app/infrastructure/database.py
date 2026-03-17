"""Factorías de conexión a bases de datos (MongoDB principal + SQLAlchemy legacy)."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


# ── MongoDB ───────────────────────────────────────────────────────────────────

def create_mongo_client(uri: str):
    """Crea un cliente pymongo con timeouts conservadores."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise ImportError(
            "pymongo no está instalado. Ejecuta: pip install pymongo"
        ) from exc

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5_000,
        connectTimeoutMS=5_000,
        socketTimeoutMS=30_000,
    )
    logger.debug("mongo_client_created", uri_prefix=uri[:30])
    return client


def get_mongo_db(client, db_name: str):
    """Devuelve la base de datos MongoDB."""
    return client[db_name]


@lru_cache(maxsize=1)
def get_cached_mongo_client(uri: str):
    """Cliente MongoDB cacheado (singleton por URI)."""
    return create_mongo_client(uri)


# ── SQLAlchemy (legacy Supabase) ───────────────────────────────────────────────

def get_engine(database_url: Optional[str] = None):
    """Devuelve el engine de SQLAlchemy. None si no hay URL configurada."""
    if not database_url:
        return None
    from sqlalchemy import create_engine
    return create_engine(database_url, pool_pre_ping=True)
