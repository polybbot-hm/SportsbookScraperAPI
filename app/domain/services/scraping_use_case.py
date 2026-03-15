"""Caso de uso: ejecutar scraping y persistir resultados."""
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domain.models import OddsSnapshot
from app.domain.ports.outbound import BookmakerScraperPort, CachePort, NotificationPort, OddsRepositoryPort


class ScrapingUseCase:
    """Orquesta scraping -> guarda en repositorio -> invalida caché -> (futuro: notificar)."""

    def __init__(
        self,
        scrapers: Dict[str, BookmakerScraperPort],
        repository: OddsRepositoryPort,
        cache: CachePort,
        notifier: Optional[NotificationPort] = None,
    ):
        self._scrapers = scrapers
        self._repository = repository
        self._cache = cache
        self._notifier = notifier

    def run(
        self,
        bookmaker: str,
        league_name: Optional[str] = None,
        target_categories=None,
        exact_league_match: bool = False,
    ) -> List[OddsSnapshot]:
        scraper = self._scrapers.get(bookmaker)
        if not scraper:
            return []
        snapshots = scraper.scrape_markets(
            league_name=league_name,
            target_categories=target_categories,
            exact_league_match=exact_league_match,
        )
        if snapshots:
            self._repository.save_snapshots(snapshots)
            self._cache.invalidate_pattern("odds:*")
        return snapshots

    def run_summary(
        self,
        bookmaker: str,
        league_name: Optional[str] = None,
        target_categories=None,
        exact_league_match: bool = False,
    ) -> Dict[str, Any]:
        """Ejecuta scraping y devuelve resumen estructurado por partido/categoría."""
        snapshots = self.run(
            bookmaker=bookmaker,
            league_name=league_name,
            target_categories=target_categories,
            exact_league_match=exact_league_match,
        )

        by_event: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
        for s in snapshots:
            by_event[s.event.match_label][s.market_type.value].add(s.market_name)

        partidos = []
        for partido, cats in by_event.items():
            partidos.append({
                "partido": partido,
                "categorias": {cat: len(mercados) for cat, mercados in cats.items()},
                "total_mercados": sum(len(m) for m in cats.values()),
            })

        return {
            "bookmaker": bookmaker,
            "liga": league_name,
            "fecha_scraping": datetime.utcnow().isoformat(),
            "total_cuotas_insertadas": len(snapshots),
            "partidos_scrapeados": len(partidos),
            "detalle": partidos,
        }
