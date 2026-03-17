"""
Scraper de cuotas — Kirolbet
=============================
Extrae todos los mercados y cuotas de los eventos de la liga configurada
parseando el HTML de la web con BeautifulSoup.
"""

import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ─── CONFIGURACIÓN FIJA ───────────────────────────────────────────────────────

_BASE_URL      = "https://apuestas.kirolbet.es"
_REQUEST_DELAY = 1.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer":         _BASE_URL,
}


# ─── FUNCIONES DE SCRAPING ───────────────────────────────────────────────────

def _get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def _get_events(competition_id: int) -> list[dict]:
    soup = _get_soup(f"{_BASE_URL}/esp/Sport/Competicion/{competition_id}")

    seen, events = set(), []
    for a in soup.find_all("a", href=re.compile(r"/esp/Sport/Evento/\d+")):
        m = re.search(r"/Evento/(\d+)", a["href"])
        if not m:
            continue
        event_id = m.group(1)
        if event_id in seen:
            continue

        name = re.sub(r"\(\+\s*\d+\)", "", a.get_text(strip=True)).strip()
        if not name or len(name) < 3:
            continue

        seen.add(event_id)
        events.append({
            "id":     event_id,
            "nombre": name,
            "url":    f"{_BASE_URL}/esp/Sport/Evento/{event_id}",
        })

    return events


def _scrape_event(event: dict) -> dict:
    soup = _get_soup(event["url"])

    fecha = None
    time_span = soup.find("span", class_=re.compile(r"fecha|date|time", re.I))
    if time_span:
        fecha = time_span.get_text(strip=True)

    nombre = event["nombre"]
    partes    = re.split(r"\s+vs\.?\s+", nombre, flags=re.I)
    local     = partes[0].strip() if len(partes) > 0 else "?"
    visitante = partes[1].strip() if len(partes) > 1 else "?"

    mercados = []
    for idx, market_el in enumerate(soup.find_all("ul", class_=re.compile(r"marketGroup"))):
        title_li = market_el.find("li")
        if not title_li:
            continue
        nombre_mercado = re.sub(r"\s+", " ", title_li.get_text(strip=True))
        if not nombre_mercado:
            continue

        cuotas = []
        for anchor in market_el.find_all("a", class_=re.compile(r"it_\d+")):
            label_span = anchor.find("span", class_="pron")
            coef_span  = anchor.find("span", class_="coef")
            if not label_span or not coef_span:
                continue
            raw = coef_span.get_text(strip=True).replace(",", ".")
            try:
                cuota_val = float(raw)
            except ValueError:
                cuota_val = raw
            cuotas.append({
                "nombre": label_span.get_text(strip=True),
                "cuota":  cuota_val,
            })

        entry = {
            "market_id":      idx,
            "nombre_mercado": nombre_mercado,
            "cuotas":         cuotas,
        }

        linea_match = re.search(r"[\+\-]?\d+(?:[.,]\d+)?", nombre_mercado)
        if linea_match and any(
            c in nombre_mercado for c in ["+", "-", "Más", "Menos", "Total"]
        ):
            raw_linea = linea_match.group().replace(",", ".")
            try:
                entry["linea"] = float(raw_linea)
            except ValueError:
                entry["linea"] = raw_linea

        mercados.append(entry)

    return {
        "event_id":  event["id"],
        "partido":   nombre,
        "local":     local,
        "visitante": visitante,
        "fecha":     fecha,
        "mercados":  mercados,
    }


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def scrape(cfg: dict, liga_nombre: str) -> dict:
    """Scraper principal. Recibe la config del bookmaker y el nombre de la liga.

    cfg esperado: {"competition_id": <int>}

    Returns:
        Dict con el formato estándar de cuotas.
    """
    competition_id = cfg["competition_id"]

    print(f"  Obteniendo eventos de {liga_nombre} (competition_id: {competition_id})...")
    events = _get_events(competition_id)
    print(f"  → {len(events)} eventos encontrados\n")

    if not events:
        print("  No se encontraron eventos.")
        return {}

    resultados = []
    for i, event in enumerate(events, 1):
        print(f"    [{i}/{len(events)}] {event['nombre']}...", end=" ", flush=True)
        try:
            data = _scrape_event(event)
            resultados.append(data)
            print(f"✅  ({len(data['mercados'])} mercados)")
        except Exception as e:
            print(f"❌ error: {e}")
        time.sleep(_REQUEST_DELAY)

    return {
        "scrape_timestamp": datetime.now().isoformat(),
        "competicion": {
            "id":     competition_id,
            "nombre": liga_nombre,
        },
        "total_eventos": len(resultados),
        "eventos":       resultados,
    }
