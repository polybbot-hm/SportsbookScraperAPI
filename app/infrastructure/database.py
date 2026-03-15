"""Conexión a base de datos. Se usará SQLAlchemy + psycopg2 para Supabase."""
from typing import Optional

# El engine se creará en el módulo de persistencia cuando haya modelos SQLAlchemy
# para no forzar conexión si no hay DATABASE_URL
def get_engine(database_url: Optional[str] = None):
    """Devuelve el engine de SQLAlchemy. None si no hay URL configurada."""
    if not database_url:
        return None
    from sqlalchemy import create_engine
    return create_engine(database_url, pool_pre_ping=True)
