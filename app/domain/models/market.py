"""Modelo de mercado de apuestas."""
from enum import Enum


class MarketType(str, Enum):
    """Tipo de mercado. Extensible para futuros mercados."""

    FALTAS = "faltas"
    PRINCIPALES = "principales"
    ESTADISTICAS = "estadisticas"
    TIROS = "tiros"
    CORNERS = "corners"
    HANDICAP = "handicap"
    RESULTADO_FINAL = "resultado_final"
    EQUIPOS = "equipos"
    TARJETAS = "tarjetas"
    GOLES = "goles"
    GOLEADORES = "goleadores"
    PRIMERA_SEGUNDA_PARTE = "primera_segunda_parte"
    ESPECIALES = "especiales"
    ASISTENCIAS = "asistencias"
    PASES = "pases"
    ENTRADAS = "entradas"
    MINUTOS = "minutos"
    COMBINADOS = "combinados"
    MATCHACCA = "matchacca"


# Mapeo de CategoryName (Codere) -> MarketType
CODERE_CATEGORY_MAP: dict = {
    "PRINCIPALES": MarketType.PRINCIPALES,
    "ESTADÍSTICAS": MarketType.ESTADISTICAS,
    "ESTADISTICAS": MarketType.ESTADISTICAS,
    "TIROS": MarketType.TIROS,
    "CORNERS": MarketType.CORNERS,
    "HANDICAP": MarketType.HANDICAP,
    "RES. FINAL": MarketType.RESULTADO_FINAL,
    "EQUIPOS": MarketType.EQUIPOS,
    "TARJETAS": MarketType.TARJETAS,
    "GOLES": MarketType.GOLES,
    "GOLEADORES": MarketType.GOLEADORES,
    "1ª/2ª PARTE": MarketType.PRIMERA_SEGUNDA_PARTE,
    "ESPECIALES": MarketType.ESPECIALES,
    "ASISTENCIAS": MarketType.ASISTENCIAS,
    "PASES": MarketType.PASES,
    "ENTRADAS": MarketType.ENTRADAS,
    "MINUTOS": MarketType.MINUTOS,
    "COMBINADOS": MarketType.COMBINADOS,
    "MATCHACCA": MarketType.MATCHACCA,
}

# Categorías que se scrapean por defecto (las que pidió el usuario)
DEFAULT_TARGET_CATEGORIES = {
    MarketType.PRINCIPALES,
    MarketType.ESTADISTICAS,
    MarketType.CORNERS,
    MarketType.HANDICAP,
    MarketType.RESULTADO_FINAL,
    MarketType.EQUIPOS,
}


def market_key(external_event_id: str, market_name: str) -> str:
    """Clave única para un mercado en un evento (evita importar Event)."""
    return f"{external_event_id}|{market_name}"
