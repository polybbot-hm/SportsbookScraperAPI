"""Servicio de normalización de mercados raw → MarketCategorySnapshot canónicos."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import structlog

from app.domain.models.market_category import (
    CATEGORY_DISPLAY_NAMES,
    CategoryKey,
    Market,
    MarketCategorySnapshot,
    Selection,
    normalize_selection_key,
)
from app.infrastructure.config_loader import MarketMapping

logger = structlog.get_logger(__name__)


class MarketNormalizer:
    """
    Convierte mercados raw de un bookmaker en MarketCategorySnapshot canónicos.

    Estrategia de mapeo (en orden de prioridad):
    1. Match exacto del nombre del mercado contra market_mappings.
    2. Match case-insensitive.
    3. Match parcial: el nombre raw contiene alguna clave del mapping.
    4. Fallback: categoría "especiales".
    """

    def __init__(self, mappings: dict[str, MarketMapping], bookmaker: str = ""):
        self._mappings = mappings
        self._bookmaker = bookmaker
        # Índice case-insensitive para lookup rápido
        self._lower_index: dict[str, tuple[str, str]] = {
            k.lower(): (v.category, v.key)
            for k, v in mappings.items()
        }

    def normalize(self, raw_markets: list[dict[str, Any]]) -> list[MarketCategorySnapshot]:
        """
        Normaliza una lista de mercados raw.

        Cada dict raw debe tener al menos:
          - nombre_mercado: str
          - cuotas: list[{"nombre": str, "cuota": float/str}]
          - market_id (opcional)
          - linea (opcional, float)

        Devuelve lista de MarketCategorySnapshot agrupados por categoría.
        """
        category_buckets: dict[str, list[Market]] = defaultdict(list)

        for raw in raw_markets:
            try:
                market = self._normalize_one(raw)
                if market is not None:
                    cat_key = self._resolve_category_key(raw)
                    category_buckets[cat_key].append(market)
            except Exception as exc:
                logger.warning(
                    "market_parse_error",
                    bookmaker=self._bookmaker,
                    raw_name=raw.get("nombre_mercado", "?"),
                    error=str(exc),
                )

        return [
            MarketCategorySnapshot(
                category_key=cat_key,
                category_name=CATEGORY_DISPLAY_NAMES.get(cat_key, cat_key.title()),
                markets=markets,
            )
            for cat_key, markets in category_buckets.items()
            if markets
        ]

    def _resolve_category_key(self, raw: dict[str, Any]) -> str:
        name = raw.get("nombre_mercado", "")
        category, _ = self._lookup(name)
        return category

    def _normalize_one(self, raw: dict[str, Any]) -> Market | None:
        name = raw.get("nombre_mercado", "")
        if not name:
            return None

        cuotas_raw = raw.get("cuotas", [])
        if not cuotas_raw:
            return None

        category_key, market_key = self._lookup(name)

        if category_key == CategoryKey.ESPECIALES:
            logger.debug(
                "normalization_fallback",
                bookmaker=self._bookmaker,
                raw_name=name,
                fallback_category=CategoryKey.ESPECIALES,
            )

        selections = self._build_selections(cuotas_raw)

        line: float | None = raw.get("linea")

        return Market(
            market_key=market_key,
            market_name=name,
            selections=selections,
            external_id=str(raw.get("market_id", "")),
            line=float(line) if line is not None else None,
        )

    def _lookup(self, raw_name: str) -> tuple[str, str]:
        """Devuelve (category_key, market_key) para el nombre del mercado raw."""
        # 1. Match exacto
        if raw_name in self._mappings:
            m = self._mappings[raw_name]
            return m.category, m.key

        # 2. Match case-insensitive
        lower = raw_name.lower().strip()
        if lower in self._lower_index:
            return self._lower_index[lower]

        # 3. Match parcial: alguna clave del mapping está contenida en el nombre raw
        for key_lower, (cat, mkt) in self._lower_index.items():
            if key_lower and key_lower in lower:
                return cat, mkt

        # 4. Fallback
        safe_key = lower.replace(" ", "_")[:40]
        return CategoryKey.ESPECIALES, safe_key

    def _build_selections(self, cuotas_raw: list[dict[str, Any]]) -> list[Selection]:
        selections: list[Selection] = []
        for c in cuotas_raw:
            nombre = c.get("nombre", "")
            cuota = c.get("cuota")
            if cuota is None:
                continue
            try:
                odds_value = float(cuota)
            except (ValueError, TypeError):
                continue
            if odds_value <= 1.0:
                continue  # cuota inválida o suspendida
            selections.append(Selection(
                key=normalize_selection_key(nombre),
                name=nombre,
                odds=round(odds_value, 4),
            ))
        return selections
