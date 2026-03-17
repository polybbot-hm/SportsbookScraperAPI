"""
Scraper de cuotas — Casino Gran Madrid (API Altenar)
────────────────────────────────────────────────────
Usa undetected-chromedriver para capturar el token de validación
que genera el SDK Altenar al cargar la web del casino, y luego
hace las peticiones desde el propio navegador para evitar bloqueos.
"""

import json
import time
from datetime import datetime
from urllib.parse import urlencode

import undetected_chromedriver as uc

# ─── CONFIGURACIÓN FIJA ───────────────────────────────────────────────────────

_BASE_URL   = "https://sb2frontend-altenar2.biahosted.com/api/widget"
_CASINO_URL = "https://www.casinogranmadridonline.es/apuestas-deportivas"

_BASE_PARAMS = {
    "culture":         "es-ES",
    "timezoneOffset":  "-60",
    "integration":     "casinogranmadrid",
    "deviceType":      "1",
    "numFormat":       "en-GB",
    "countryCode":     "ES",
}

_REQUEST_DELAY = 0.5

_INTERCEPT_JS = """
window.__altenarHeaders = [];

(function() {
    const origFetch = window.fetch;
    window.fetch = function(resource, init) {
        const url = (typeof resource === 'string') ? resource
                  : (resource && resource.url) ? resource.url : '';
        if (url.includes('sb2frontend-altenar')) {
            const h = {};
            if (init && init.headers) {
                if (init.headers instanceof Headers) {
                    for (const [k,v] of init.headers.entries()) h[k] = v;
                } else if (typeof init.headers === 'object') {
                    Object.keys(init.headers).forEach(k => h[k] = init.headers[k]);
                }
            }
            h['__url'] = url;
            window.__altenarHeaders.push(h);
        }
        return origFetch.apply(this, arguments);
    };

    const origOpen      = XMLHttpRequest.prototype.open;
    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    const origSend      = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url) {
        this.__capturedUrl     = (typeof url === 'string') ? url : '';
        this.__capturedHeaders = {};
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(key, value) {
        if (this.__capturedUrl && this.__capturedUrl.includes('sb2frontend-altenar')) {
            this.__capturedHeaders[key] = value;
        }
        return origSetHeader.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function() {
        if (this.__capturedUrl && this.__capturedUrl.includes('sb2frontend-altenar')) {
            const copy = Object.assign({}, this.__capturedHeaders);
            copy['__url'] = this.__capturedUrl;
            window.__altenarHeaders.push(copy);
        }
        return origSend.apply(this, arguments);
    };
})();
"""


# ─── CLIENTE ALTENAR ─────────────────────────────────────────────────────────

class _AltenarClient:
    """Abre Chrome, captura el token Altenar y expone métodos de consulta."""

    def __init__(self):
        print("  Iniciando navegador Chrome...")
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=es-ES")

        self.driver = uc.Chrome(options=options, version_main=145)
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": _INTERCEPT_JS},
        )

        print("  Cargando Casino Gran Madrid (capturando token)...")
        self.driver.get(_CASINO_URL)
        time.sleep(15)

        captured = self.driver.execute_script(
            "return window.__altenarHeaders || [];"
        )

        self.auth_token = None
        for entry in captured:
            url  = entry.get("__url", "")
            auth = entry.get("Authorization") or entry.get("authorization")
            if "sb2frontend-altenar" in url and auth:
                self.auth_token = auth
                break

        if self.auth_token:
            print(f"  Token capturado: {self.auth_token[:40]}...")
        else:
            print("  ⚠️  No se capturó token (se intentará sin él)")
        print("  Sesión lista.\n")

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def _get(self, endpoint: str, extra_params: dict = None) -> dict | None:
        params = {**_BASE_PARAMS, **(extra_params or {})}
        url    = f"{_BASE_URL}/{endpoint}?{urlencode(params)}"

        headers_js = "{}"
        if self.auth_token:
            safe_token = self.auth_token.replace("'", "\\'")
            headers_js = "{'Authorization': '" + safe_token + "'}"

        js = """
        var url = arguments[0];
        var callback = arguments[arguments.length - 1];
        fetch(url, {
            method: 'GET',
            headers: """ + headers_js + """
        })
        .then(function(r) {
            if (!r.ok) return r.text().then(function(t) {
                callback(JSON.stringify({__http_error: r.status, body: t}));
            });
            return r.text().then(function(t) { callback(t); });
        })
        .catch(function(e) {
            callback(JSON.stringify({__fetch_error: e.message}));
        });
        """

        for attempt in range(3):
            try:
                raw = self.driver.execute_async_script(js, url)
                if not raw:
                    print(f"  ⚠️  Respuesta vacía (intento {attempt+1}/3)")
                    time.sleep(_REQUEST_DELAY)
                    continue

                data = json.loads(raw)

                if isinstance(data, dict) and "__http_error" in data:
                    print(f"  ⚠️  HTTP {data['__http_error']} (intento {attempt+1}/3)")
                    time.sleep(_REQUEST_DELAY * 2)
                    continue
                if isinstance(data, dict) and "__fetch_error" in data:
                    print(f"  ⚠️  Fetch error: {data['__fetch_error']} (intento {attempt+1}/3)")
                    time.sleep(_REQUEST_DELAY * 2)
                    continue

                return data

            except json.JSONDecodeError:
                print(f"  ⚠️  JSON inválido (intento {attempt+1}/3)")
                time.sleep(_REQUEST_DELAY)
            except Exception as e:
                print(f"  ⚠️  Error ({attempt+1}/3): {e}")
                time.sleep(_REQUEST_DELAY)

        return None

    def get_events(self, champ_id: int) -> dict | None:
        return self._get("GetEvents", {
            "eventCount": "0",
            "sportId":    "0",
            "champIds":   str(champ_id),
        })

    def get_event_details(self, event_id: int) -> dict | None:
        return self._get("GetEventDetails", {
            "eventId":      str(event_id),
            "showNonBoosts": "false",
        })


# ─── LÓGICA DE EXTRACCIÓN ───────────────────────────────────────────────────

def _extract_all_odds(detail: dict) -> list[dict]:
    odds_lookup = {o["id"]: o for o in detail.get("odds", [])}
    mercados = []

    for market in detail.get("markets", []):
        odd_ids = [
            oid
            for sublist in market.get("desktopOddIds", [])
            for oid in sublist
        ]

        cuotas = [
            {"nombre": odds_lookup[oid]["name"], "cuota": odds_lookup[oid]["price"]}
            for oid in odd_ids
            if oid in odds_lookup
        ]

        entry = {
            "market_id":      market["id"],
            "market_type_id": market["typeId"],
            "nombre_mercado": market["name"],
            "cuotas":         cuotas,
        }
        if market.get("sv"):
            sv_raw = market["sv"].split("|")[0]
            try:
                entry["linea"] = float(sv_raw)
            except ValueError:
                entry["linea"] = sv_raw

        mercados.append(entry)

    return mercados


def _scrape_events(client: _AltenarClient, champ_id: int) -> list[dict]:
    events_data = client.get_events(champ_id)
    if not events_data:
        return []

    events = events_data.get("events", [])
    if not events:
        return []

    competitors_lookup = {
        c["id"]: c["name"].strip()
        for c in events_data.get("competitors", [])
    }

    resultados = []
    for i, event in enumerate(events, 1):
        nombre = event["name"].strip()
        print(f"    [{i}/{len(events)}] {nombre}...", end=" ", flush=True)

        try:
            detail = client.get_event_details(event["id"])
            if not detail:
                print("⚠️  sin datos")
                time.sleep(_REQUEST_DELAY)
                continue

            mercados  = _extract_all_odds(detail)
            comp_ids  = event.get("competitorIds", [])
            local     = competitors_lookup.get(comp_ids[0], "?") if len(comp_ids) > 0 else "?"
            visitante = competitors_lookup.get(comp_ids[1], "?") if len(comp_ids) > 1 else "?"

            resultados.append({
                "event_id":  event["id"],
                "partido":   nombre,
                "local":     local,
                "visitante": visitante,
                "fecha":     event["startDate"],
                "mercados":  mercados,
            })
            print(f"✅  ({len(mercados)} mercados)")

        except Exception as e:
            print(f"❌ error: {e}")

        time.sleep(_REQUEST_DELAY)

    return resultados


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def scrape(cfg: dict, liga_nombre: str) -> dict:
    """Scraper principal. Recibe la config del bookmaker y el nombre de la liga.

    cfg esperado: {"champ_id": <int>}

    Returns:
        Dict con el formato estándar de cuotas.
    """
    champ_id = cfg["champ_id"]

    client = _AltenarClient()
    try:
        print(f"  Obteniendo eventos de {liga_nombre} (champ_id: {champ_id})...\n")
        eventos = _scrape_events(client, champ_id)
    finally:
        client.close()

    if not eventos:
        print("  No se obtuvieron eventos.")
        return {}

    return {
        "scrape_timestamp": datetime.now().isoformat(),
        "competicion": {
            "id":     champ_id,
            "nombre": liga_nombre,
        },
        "total_eventos": len(eventos),
        "eventos":       eventos,
    }
