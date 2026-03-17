"""Modelos de categorías de mercado, submercados y selecciones."""
from dataclasses import dataclass, field
from typing import Optional


# ── Claves canónicas de categorías ────────────────────────────────────────────

class CategoryKey:
    RESULTADO = "resultado"
    TOTALES = "totales"
    HANDICAP = "handicap"
    AMBOS_MARCAN = "ambos_marcan"
    MARCADOR_EXACTO = "marcador_exacto"
    PRIMER_GOL = "primer_gol"
    MITAD = "mitad"
    CORNERS = "corners"
    TARJETAS = "tarjetas"
    FALTAS = "faltas"
    ESPECIALES = "especiales"

    ALL: list[str] = [
        RESULTADO, TOTALES, HANDICAP, AMBOS_MARCAN, MARCADOR_EXACTO,
        PRIMER_GOL, MITAD, CORNERS, TARJETAS, FALTAS, ESPECIALES,
    ]


CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    CategoryKey.RESULTADO:       "Resultado",
    CategoryKey.TOTALES:         "Totales",
    CategoryKey.HANDICAP:        "Hándicap",
    CategoryKey.AMBOS_MARCAN:    "Ambos Marcan",
    CategoryKey.MARCADOR_EXACTO: "Marcador Exacto",
    CategoryKey.PRIMER_GOL:      "Primer Goleador",
    CategoryKey.MITAD:           "Primera / Segunda Parte",
    CategoryKey.CORNERS:         "Corners",
    CategoryKey.TARJETAS:        "Tarjetas",
    CategoryKey.FALTAS:          "Faltas",
    CategoryKey.ESPECIALES:      "Especiales",
}

# ── Claves canónicas de selecciones ───────────────────────────────────────────

SELECTION_KEY_MAP: dict[str, str] = {
    # Resultado partido
    "1": "home", "local": "home", "home": "home",
    "x": "draw", "empate": "draw", "draw": "draw",
    "2": "away", "visitante": "away", "away": "away",
    # Over / under
    "más": "over", "mas": "over", "over": "over", "+": "over",
    "menos": "under", "under": "under", "-": "under",
    # BTTS
    "sí": "yes", "si": "yes", "yes": "yes",
    "no": "no",
}


def normalize_selection_key(raw: str) -> str:
    """Devuelve la clave canónica de una selección o el original en minúsculas."""
    lowered = raw.strip().lower()
    return SELECTION_KEY_MAP.get(lowered, lowered)


# ── Clases de datos ───────────────────────────────────────────────────────────

@dataclass
class Selection:
    """Una selección dentro de un mercado (1, X, 2, Over, Under…)."""

    key: str           # clave canónica: "home", "draw", "away", "over", "under"…
    name: str          # nombre tal como lo devuelve la casa
    odds: float


@dataclass
class Market:
    """Un submercado dentro de una categoría (p.ej. 1X2, Over/Under 2.5…)."""

    market_key: str            # clave normalizada: "1x2", "over_under"…
    market_name: str           # nombre tal como lo devuelve la casa
    selections: list[Selection] = field(default_factory=list)
    external_id: Optional[str] = None   # ID interno de la casa (si lo hay)
    line: Optional[float] = None        # línea del mercado (2.5, 3.5, etc.)

    @property
    def has_odds(self) -> bool:
        return bool(self.selections)


@dataclass
class MarketCategorySnapshot:
    """Colección de submercados bajo una categoría canónica, para un evento y bookmaker."""

    category_key: str    # clave canónica del dominio (CategoryKey.*)
    category_name: str   # nombre legible
    markets: list[Market] = field(default_factory=list)

    @property
    def total_markets(self) -> int:
        return len(self.markets)
