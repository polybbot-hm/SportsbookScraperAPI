"""
main.py — Orquestador de scrapers de cuotas deportivas
=======================================================
Lee config.yaml, selecciona la liga activa y lanza los scrapers
de cada bookmaker, guardando los resultados en data/{liga}/.

Uso:
    python main.py                        # todos los bookmakers
    python main.py --bookmaker speedy     # solo SpeedyBet
    python main.py --bookmaker granmadrid # solo Casino Gran Madrid
    python main.py --bookmaker kirol      # solo Kirolbet
    python main.py --liga premier_league  # fuerza una liga concreta
"""

import argparse
import sys
import time
from pathlib import Path

import yaml

from scrapers import granmadrid, kirol, speedy
from utils.storage import save_json

# ─── REGISTRO DE SCRAPERS ─────────────────────────────────────────────────────

SCRAPERS: dict[str, callable] = {
    "speedy":     speedy.scrape,
    "granmadrid": granmadrid.scrape,
    "kirol":      kirol.scrape,
}


# ─── CARGA DE CONFIG ──────────────────────────────────────────────────────────

def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        sys.exit(f"❌ No se encontró config.yaml en {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scraper de cuotas deportivas — multi-bookmaker"
    )
    parser.add_argument(
        "--bookmaker", "-b",
        choices=[*SCRAPERS.keys(), "all"],
        default="all",
        metavar="BOOKMAKER",
        help=f"Bookmaker a scrapear: {', '.join(SCRAPERS)} (default: all)",
    )
    parser.add_argument(
        "--liga", "-l",
        default=None,
        metavar="LIGA",
        help="Sobreescribe la liga activa definida en config.yaml",
    )
    args = parser.parse_args()

    cfg      = load_config()
    liga_key = args.liga or cfg["liga_activa"]

    if liga_key not in cfg["ligas"]:
        available = ", ".join(cfg["ligas"].keys())
        sys.exit(f"❌ Liga '{liga_key}' no existe en config.yaml. Disponibles: {available}")

    liga_cfg    = cfg["ligas"][liga_key]
    liga_nombre = liga_cfg["nombre"]
    targets     = list(SCRAPERS.keys()) if args.bookmaker == "all" else [args.bookmaker]

    print(f"\n{'═' * 55}")
    print(f"  Liga:        {liga_nombre}  ({liga_key})")
    print(f"  Bookmakers:  {', '.join(targets)}")
    print(f"{'═' * 55}\n")

    resultados_globales = {}
    tiempo_inicio = time.time()

    for name in targets:
        bm_cfg = liga_cfg.get("bookmakers", {}).get(name)

        print(f"{'─' * 55}")
        print(f"  Bookmaker: {name.upper()}")
        print(f"{'─' * 55}")

        if not bm_cfg:
            print(f"  ⚠️  Sin configuración para '{liga_nombre}'. Se omite.\n")
            continue

        if any(v is None for v in bm_cfg.values()):
            print(f"  ⚠️  IDs pendientes de configurar para '{liga_nombre}'. Se omite.\n")
            continue

        try:
            t0   = time.time()
            data = SCRAPERS[name](bm_cfg, liga_nombre)
            elapsed = round(time.time() - t0, 1)

            if not data or not data.get("eventos"):
                print(f"  ⚠️  Sin datos obtenidos ({elapsed}s).\n")
                continue

            path = save_json(data, name, liga_key)
            resultados_globales[name] = {
                "eventos": data["total_eventos"],
                "archivo": str(path),
                "tiempo":  elapsed,
            }
            print(f"\n  ✅ Guardado en: {path}  ({elapsed}s)\n")

        except Exception as e:
            print(f"\n  ❌ Error en {name}: {e}\n")

    # ── Resumen final ────────────────────────────────────────────────────────
    total = round(time.time() - tiempo_inicio, 1)
    print(f"\n{'═' * 55}")
    print(f"  RESUMEN — {liga_nombre}")
    print(f"{'═' * 55}")
    for bm, info in resultados_globales.items():
        print(f"  {bm:<12}  {info['eventos']} eventos  →  {info['archivo']}")
    if not resultados_globales:
        print("  Sin resultados.")
    print(f"\n  Tiempo total: {total}s")
    print(f"{'═' * 55}\n")


if __name__ == "__main__":
    main()
