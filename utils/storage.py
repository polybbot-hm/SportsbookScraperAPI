"""
Utilidad para guardar los resultados del scraping en la carpeta data/.

Estructura de salida:
    data/
    └── {liga_key}/
        └── {bookmaker}_{YYYYMMDD_HHMMSS}.json
"""

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def save_json(data: dict, bookmaker: str, liga_key: str) -> Path:
    """Guarda `data` en data/{liga_key}/{bookmaker}_{timestamp}.json.

    Returns:
        Path al archivo creado.
    """
    liga_dir = DATA_DIR / liga_key
    liga_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = liga_dir / f"{bookmaker}_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def latest_json(bookmaker: str, liga_key: str) -> Path | None:
    """Devuelve el JSON más reciente de un bookmaker para una liga, o None."""
    liga_dir = DATA_DIR / liga_key
    if not liga_dir.exists():
        return None

    files = sorted(liga_dir.glob(f"{bookmaker}_*.json"), reverse=True)
    return files[0] if files else None
