"""
Scraper de cuotas — SpeedyBet (Kambi API)
=========================================
Extrae todos los mercados y cuotas de los eventos de la liga configurada.
"""

import time
from datetime import datetime

import requests

# ─── CLIENTE API ──────────────────────────────────────────────────────────────

_BASE_URL = "https://eu1.offering-api.kambicdn.com/offering/v2018/pafspeedybetes"

_DEFAULT_PARAMS = {
    "lang":       "es_ES",
    "market":     "ES",
    "client_id":  200,
    "channel_id": 1,
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_REQUEST_DELAY = 0.5


def _api_get(endpoint: str, extra_params: dict = None) -> dict:
    url    = f"{_BASE_URL}/{endpoint}"
    params = {**_DEFAULT_PARAMS, **(extra_params or {})}
    resp   = requests.get(url, params=params, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _get_events(group_id: int) -> list[dict]:
    data = _api_get(f"event/group/{group_id}.json")
    events = [
        {
            "id":    e["id"],
            "name":  e.get("name", ""),
            "home":  e.get("homeName", ""),
            "away":  e.get("awayName", ""),
            "start": e.get("start", ""),
        }
        for e in data.get("events", [])
    ]
    events.sort(key=lambda x: x["start"])
    return events


def _get_all_markets(event_id: int) -> list[dict]:
    data = _api_get(
        f"betoffer/event/{event_id}.json",
        extra_params={
            "include":        "all",
            "categoryGroup":  "COMBINED",
            "displayDefault": "true",
        },
    )

    mercados = []
    for idx, offer in enumerate(data.get("betOffers", [])):
        criterion = offer.get("criterion", {})
        cuotas = []
        for outcome in offer.get("outcomes", []):
            if "odds" not in outcome:
                continue
            entry = {
                "nombre": outcome.get("label", ""),
                "cuota":  round(outcome["odds"] / 1000, 4),
            }
            if outcome.get("line") is not None:
                entry["linea"] = outcome["line"] / 1000
            cuotas.append(entry)

        market = {
            "market_id":      offer.get("id", idx),
            "market_type_id": criterion.get("id"),
            "nombre_mercado": criterion.get("label", ""),
            "cuotas":         cuotas,
        }

        lines = {c["linea"] for c in cuotas if "linea" in c}
        if len(lines) == 1:
            market["linea"] = lines.pop()

        mercados.append(market)

    return mercados


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def scrape(cfg: dict, liga_nombre: str) -> dict:
    """Scraper principal. Recibe la config del bookmaker y el nombre de la liga.

    cfg esperado: {"group_id": <int>}

    Returns:
        Dict con el formato estándar de cuotas.
    """
    group_id = cfg["group_id"]

    print(f"  Obteniendo eventos de {liga_nombre} (group_id: {group_id})...")
    events = _get_events(group_id)
    print(f"  → {len(events)} eventos encontrados\n")

    if not events:
        print("  No se encontraron eventos.")
        return {}

    resultados = []
    for i, event in enumerate(events, 1):
        print(f"    [{i}/{len(events)}] {event['name']}...", end=" ", flush=True)
        try:
            mercados = _get_all_markets(event["id"])
            resultados.append({
                "event_id":  event["id"],
                "partido":   event["name"],
                "local":     event["home"],
                "visitante": event["away"],
                "fecha":     event["start"],
                "mercados":  mercados,
            })
            print(f"✅  ({len(mercados)} mercados)")
        except Exception as e:
            print(f"❌ error: {e}")

        time.sleep(_REQUEST_DELAY)

    return {
        "scrape_timestamp": datetime.now().isoformat(),
        "competicion": {
            "id":     group_id,
            "nombre": liga_nombre,
        },
        "total_eventos": len(resultados),
        "eventos":       resultados,
    }
