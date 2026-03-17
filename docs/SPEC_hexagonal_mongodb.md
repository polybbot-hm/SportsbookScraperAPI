# Especificación técnica: Expansión con Arquitectura Hexagonal y MongoDB

**Versión:** 1.0  
**Fecha:** 2026-03-17  
**Proyecto:** SportsbookScraperAPI

---

## 1. Contexto y situación actual

### 1.1 Estado de la aplicación

La aplicación tiene **dos capas paralelas que conviven sin integrarse**:

| Capa | Ruta | Estado |
|---|---|---|
| Scrapers standalone (CLI) | `scrapers/`, `main.py`, `config.yaml` | Funcional. Tres scrapers operativos: SpeedyBet, GranMadrid, Kirolbet |
| API hexagonal (FastAPI) | `app/` | Funcional pero solo con Codere como scraper implementado |

Los scrapers standalone producen JSONs locales con una estructura informal (campos en español, sin tipado, sin normalización de mercados). La API hexagonal tiene puertos, servicios y adaptadores bien definidos pero sus scrapers de referencia (PAF, Retabet) son `NotImplementedError`.

### 1.2 Scrapers existentes a integrar

| Bookmaker | Tecnología de scraping | Identificador config |
|---|---|---|
| **SpeedyBet** | API REST pública Kambi (`eu1.offering-api.kambicdn.com`) | `group_id` |
| **Casino Gran Madrid** | API Altenar capturando token via `undetected_chromedriver` | `champ_id` |
| **Kirolbet** | HTML scraping con `requests` + `BeautifulSoup` | `competition_id` |

### 1.3 Problemas identificados

1. Los scrapers no están integrados en la arquitectura hexagonal de `app/`.
2. No existe normalización de mercados entre casas: cada bookmaker devuelve nombres de mercado distintos para el mismo concepto (ej. "1X2", "1x2", "Match Result", "Resultado 1X2").
3. La persistencia SQL (Supabase) es rígida para mercados heterogéneos: algunos mercados existen en unas casas y no en otras.
4. La configuración está fragmentada entre `config.yaml` (scrapers CLI), `.env` / `app/config.py` (Pydantic Settings) y valores hardcodeados dentro de cada scraper.
5. El manejo de errores se limita a `try/except` con `print()`. No hay logging estructurado en los scrapers.
6. `BookmakerName` solo tiene `CODERE`, `PAF`, `RETABET`; los nuevos no existen en el dominio.

---

## 2. Objetivos de la feature

1. **Integrar** los tres scrapers (`speedy`, `granmadrid`, `kirol`) en la arquitectura hexagonal como adaptadores outbound que implementan `BookmakerScraperPort`.
2. **Definir un dominio de mercados** flexible basado en categorías y submercados, tolerante a la ausencia de mercados en ciertas casas.
3. **Reemplazar la persistencia SQL** por **MongoDB** con un modelo de documento que capture la heterogeneidad de mercados de forma natural.
4. **Centralizar la configuración** en archivos YAML (aplicación + scrapers), eliminando valores hardcodeados en los adaptadores.
5. **Añadir logging estructurado** con `structlog` en todos los componentes y **manejo de errores** homogéneo con jerarquía de excepciones de dominio.

---

## 3. Diseño del dominio

### 3.1 Modelo de mercados: categorías y submercados

El problema central es que cada bookmaker ofrece un subconjunto distinto de mercados y los nombra de forma diferente. La solución es un **modelo de dos niveles** con normalización:

```
MarketCategory (categoría canónica)
└── Market (submercado dentro de la categoría)
    └── Selection (selección con su cuota)
```

**Categorías canónicas definidas en el dominio:**

| `category_key` | Descripción | Ejemplos de mercados dentro |
|---|---|---|
| `resultado` | Resultado final del partido | 1X2, Doble Oportunidad, Resultado Doble |
| `totales` | Over/Under de goles | Más/Menos 2.5, Asian Total, Total Goles |
| `handicap` | Ventajas | Hándicap Europeo, Hándicap Asiático |
| `ambos_marcan` | BTTS | Ambos Equipos Marcan |
| `marcador_exacto` | Marcador exacto | Resultado Exacto |
| `primer_gol` | Goleadores | Primer Goleador, Último Goleador |
| `mitad` | Mercados de primera/segunda parte | Resultado 1ª Parte, Total 1ª Parte |
| `corners` | Saques de esquina | Total Corners, Corners 1ª Parte |
| `tarjetas` | Tarjetas | Total Tarjetas, Ambos con Tarjeta |
| `faltas` | Faltas | Total Faltas, Equipo con Más Faltas |
| `especiales` | Mercados propios de la casa | Cuotas mejoradas, mercados propios |

> Las categorías son **extensibles**: se puede añadir una nueva categoría sin modificar el esquema de base de datos.

### 3.2 Entidades de dominio

```
Sport
  id: str  ("football", "basketball", ...)
  name: str

Competition
  external_id: str          # ID de la casa (group_id, champ_id, ...)
  bookmaker: BookmakerName
  name: str
  sport: str
  normalized_key: str       # slug canónico: "la_liga", "premier_league", ...

Event
  external_id: str
  bookmaker: BookmakerName
  competition_key: str      # FK lógica a Competition.normalized_key
  home_team: str
  away_team: str
  event_date: datetime | None
  normalized_key: str       # slug: "villarreal_real-sociedad_20260320"

MarketCategory
  category_key: str         # clave canónica del dominio (ej. "resultado")
  category_name: str        # nombre legible

Market
  market_key: str           # clave normalizada (ej. "1x2", "over_under_2_5")
  market_name: str          # nombre tal como lo devuelve la casa
  external_id: str | None   # ID interno de la casa (si lo hay)
  line: float | None        # línea del mercado (ej. 2.5 para over/under)
  selections: list[Selection]

Selection
  key: str                  # clave canónica ("home", "draw", "away", "over", "under", ...)
  name: str                 # nombre tal como lo devuelve la casa
  odds: float

OddsSnapshot
  id: str                   # UUID generado
  bookmaker: BookmakerName
  competition: Competition
  event: Event
  scraped_at: datetime
  market_categories: list[MarketCategorySnapshot]

MarketCategorySnapshot
  category_key: str
  category_name: str
  markets: list[Market]
```

### 3.3 Clave de normalización de eventos (`normalized_key`)

Para poder cruzar datos entre casas, cada evento debe tener una clave canónica que sea **independiente del bookmaker**. Se genera así:

```python
def build_event_key(home: str, away: str, date: date | None) -> str:
    slug = lambda s: re.sub(r"[^a-z0-9]", "-", s.lower().strip())
    date_part = date.strftime("%Y%m%d") if date else "nodate"
    return f"{slug(home)}_{slug(away)}_{date_part}"
```

Esta clave permite al endpoint `/compare/{event_key}` agregar cuotas de todas las casas para el mismo partido.

### 3.4 Tabla de normalización de mercados

Cada adaptador incluye un mapa `raw_market_name → (category_key, market_key)` que se define en el YAML de configuración del bookmaker (ver sección 5). Los mercados no mapeados caen en `especiales`.

Ejemplo para SpeedyBet:

```yaml
market_mappings:
  "Match Result":             { category: "resultado",  key: "1x2" }
  "Double Chance":            { category: "resultado",  key: "doble_oportunidad" }
  "Over/Under":               { category: "totales",    key: "over_under" }
  "Asian Total":              { category: "totales",    key: "asian_total" }
  "Asian Handicap":           { category: "handicap",   key: "asian_handicap" }
  "Both Teams to Score":      { category: "ambos_marcan", key: "btts" }
  "Corners Over/Under":       { category: "corners",    key: "total_corners" }
```

---

## 4. Arquitectura hexagonal: estructura de carpetas objetivo

```
app/
├── domain/
│   ├── models/
│   │   ├── bookmaker.py          # BookmakerName enum (añadir SPEEDY, GRANMADRID, KIROL)
│   │   ├── competition.py        # Competition dataclass (nuevo)
│   │   ├── event.py              # Event dataclass (añadir normalized_key)
│   │   ├── market.py             # MarketCategory, Market, Selection (refactor completo)
│   │   ├── odds_snapshot.py      # OddsSnapshot (refactor: incluye market_categories)
│   │   └── __init__.py
│   ├── ports/
│   │   ├── inbound/
│   │   │   ├── odds_query_port.py
│   │   │   ├── scraping_service_port.py
│   │   │   └── comparison_service_port.py
│   │   └── outbound/
│   │       ├── scraper_port.py           # BookmakerScraperPort (sin cambios de interfaz)
│   │       ├── odds_repository_port.py   # OddsRepositoryPort (adaptar firmas a nuevo modelo)
│   │       ├── cache_port.py
│   │       ├── notification_port.py
│   │       └── calendar_port.py
│   ├── services/
│   │   ├── scraping_use_case.py          # Sin cambios de lógica
│   │   ├── comparison_use_case.py        # Adaptar al nuevo normalized_key
│   │   ├── market_normalizer.py          # NUEVO: normaliza raw → MarketCategory
│   │   ├── daily_job_service.py
│   │   └── odds_formatter.py
│   └── exceptions.py                     # NUEVO: jerarquía de excepciones de dominio
├── adapters/
│   ├── inbound/
│   │   └── api/
│   │       ├── routes/
│   │       │   ├── scraping_routes.py
│   │       │   ├── odds_routes.py
│   │       │   ├── comparison_routes.py
│   │       │   └── bookmakers_routes.py
│   │       ├── schemas/
│   │       │   ├── requests.py
│   │       │   └── responses.py
│   │       └── dependencies.py           # Refactor: inyectar MongoDB repo
│   └── outbound/
│       ├── scrapers/
│       │   ├── speedy_scraper.py         # NUEVO: adapta scrapers/speedy.py
│       │   ├── granmadrid_scraper.py     # NUEVO: adapta scrapers/granmadrid.py
│       │   ├── kirol_scraper.py          # NUEVO: adapta scrapers/kirol.py
│       │   ├── codere_scraper.py         # Existente (mantener)
│       │   └── base_scraper.py           # NUEVO: clase base con retry/logging
│       ├── persistence/
│       │   ├── mongo_repository.py       # NUEVO: implementa OddsRepositoryPort
│       │   ├── mongo_models.py           # NUEVO: estructura de documentos Mongo
│       │   ├── memory_repository.py      # Mantener para tests/fallback
│       │   └── (supabase_repository.py)  # Deprecar gradualmente
│       ├── cache/
│       │   └── in_memory_cache.py
│       └── notifications/
│           └── notification_adapter.py
├── infrastructure/
│   ├── config_loader.py          # NUEVO: carga config.yaml + bookmakers YAML
│   ├── http_client.py
│   ├── rate_limiter.py
│   ├── database.py               # Añadir MongoDB client factory
│   └── logging_config.py        # Ampliar: contexto de bookmaker/event en logs
├── main.py
└── config.py                     # Pydantic Settings: añadir campos MongoDB
```

---

## 5. Configuración centralizada en YAML

### 5.1 `config/app.yaml` — configuración global de la aplicación

```yaml
app:
  name: SportsbookScraperAPI
  debug: false
  timezone: Europe/Madrid

scraping:
  delay_min: 0.3
  delay_max: 0.8
  cron: "0 */6 * * *"
  retry:
    max_attempts: 3
    wait_min: 1.0
    wait_max: 5.0

mongodb:
  database: sportsbook_scraper
  collection_snapshots: odds_snapshots
  collection_events: events

cache:
  ttl_seconds: 300

calendar:
  file_path: config/laliga_calendar.json

logging:
  level: INFO        # DEBUG | INFO | WARNING | ERROR
  format: json       # json | console
  output: stdout     # stdout | file
  file_path: logs/app.log
```

### 5.2 `config/bookmakers/speedy.yaml`

```yaml
bookmaker: speedy
name: SpeedyBet
enabled: true
api:
  base_url: "https://eu1.offering-api.kambicdn.com/offering/v2018/pafspeedybetes"
  client_id: 200
  channel_id: 1
  lang: "es_ES"
  market: "ES"
  timeout: 15
  request_delay: 0.5
headers:
  User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  Accept: "application/json"
market_mappings:
  "Match Result":             { category: "resultado",     key: "1x2" }
  "Double Chance":            { category: "resultado",     key: "doble_oportunidad" }
  "Over/Under":               { category: "totales",       key: "over_under" }
  "Asian Total":              { category: "totales",       key: "asian_total" }
  "Asian Handicap":           { category: "handicap",      key: "asian_handicap" }
  "Both Teams to Score":      { category: "ambos_marcan",  key: "btts" }
  "Corners - Over/Under":     { category: "corners",       key: "total_corners" }
  "Correct Score":            { category: "marcador_exacto", key: "resultado_exacto" }
  "1st Half - Over/Under":    { category: "mitad",         key: "total_1a_parte" }
  "1st Half - Result":        { category: "mitad",         key: "resultado_1a_parte" }
```

### 5.3 `config/bookmakers/granmadrid.yaml`

```yaml
bookmaker: granmadrid
name: Casino Gran Madrid
enabled: true
api:
  base_url: "https://sb2frontend-altenar2.biahosted.com/api/widget"
  casino_url: "https://www.casinogranmadridonline.es/apuestas-deportivas"
  culture: "es-ES"
  timezone_offset: "-60"
  integration: "casinogranmadrid"
  device_type: 1
  num_format: "en-GB"
  country_code: "ES"
  request_delay: 0.5
  token_wait_seconds: 15
browser:
  headless: true
  window_size: "1920,1080"
  lang: "es-ES"
market_mappings:
  "1x2":                { category: "resultado",      key: "1x2" }
  "Doble Oportunidad":  { category: "resultado",      key: "doble_oportunidad" }
  "Total":              { category: "totales",        key: "over_under" }
  "Hándicap Asiático":  { category: "handicap",       key: "asian_handicap" }
  "Hándicap Europeo":   { category: "handicap",       key: "handicap_europeo" }
  "Ambos Equipos Marcan": { category: "ambos_marcan", key: "btts" }
  "Resultado Exacto":   { category: "marcador_exacto", key: "resultado_exacto" }
```

### 5.4 `config/bookmakers/kirol.yaml`

```yaml
bookmaker: kirol
name: Kirolbet
enabled: true
web:
  base_url: "https://apuestas.kirolbet.es"
  request_delay: 1.0
  timeout: 15
headers:
  User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  Accept-Language: "es-ES,es;q=0.9"
  Accept: "text/html,application/xhtml+xml,*/*;q=0.8"
market_mappings:
  "1X2":                 { category: "resultado",      key: "1x2" }
  "Doble Oportunidad":   { category: "resultado",      key: "doble_oportunidad" }
  "Resultado Exacto":    { category: "marcador_exacto", key: "resultado_exacto" }
  "Más de":              { category: "totales",        key: "over_under" }
  "Menos de":            { category: "totales",        key: "over_under" }
  "Total Goles":         { category: "totales",        key: "over_under" }
  "Ambos Equipos Marcan": { category: "ambos_marcan",  key: "btts" }
```

### 5.5 `config/leagues.yaml` — ligas por bookmaker

```yaml
active_league: la_liga

leagues:
  la_liga:
    name: "La Liga"
    sport: football
    bookmakers:
      speedy:
        group_id: 1000095049
      granmadrid:
        champ_id: 2941
      kirol:
        competition_id: 1
      codere:
        sport_handle: "futbol"
        league_handle: "primera-division"

  premier_league:
    name: "Premier League"
    sport: football
    bookmakers:
      speedy:
        group_id: null
      granmadrid:
        champ_id: null
      kirol:
        competition_id: null
      codere:
        sport_handle: null

  bundesliga:
    name: "Bundesliga"
    sport: football
    bookmakers:
      speedy:
        group_id: null
      granmadrid:
        champ_id: null
      kirol:
        competition_id: null
```

### 5.6 Cargador de configuración: `app/infrastructure/config_loader.py`

```python
class ConfigLoader:
    """Carga y fusiona config/app.yaml + config/leagues.yaml + config/bookmakers/*.yaml."""

    def load_app_config(self) -> AppConfig: ...
    def load_leagues(self) -> dict[str, LeagueConfig]: ...
    def load_bookmaker(self, name: str) -> BookmakerConfig: ...
    def load_all_bookmakers(self) -> dict[str, BookmakerConfig]: ...
```

Las clases `AppConfig`, `LeagueConfig`, `BookmakerConfig` son Pydantic models validados al arrancar la app. `app/config.py` (Pydantic Settings) se mantiene **solo para secretos** (`MONGO_URI`, `SUPABASE_KEY`, variables de entorno sensibles); todo lo demás viene del YAML.

---

## 6. Modelo de datos MongoDB

### 6.1 Colección `odds_snapshots`

Cada documento representa **un scrape completo de un bookmaker para un evento**:

```json
{
  "_id": "ObjectId",
  "snapshot_id": "uuid-v4",
  "bookmaker": "speedy",
  "scraped_at": "2026-03-17T12:51:17Z",
  "competition": {
    "external_id": "1000095049",
    "name": "La Liga",
    "normalized_key": "la_liga",
    "sport": "football"
  },
  "event": {
    "external_id": "1234567",
    "home_team": "Villarreal CF",
    "away_team": "Real Sociedad",
    "event_date": "2026-03-20T20:00:00Z",
    "normalized_key": "villarreal-cf_real-sociedad_20260320"
  },
  "market_categories": [
    {
      "category_key": "resultado",
      "category_name": "Resultado",
      "markets": [
        {
          "market_key": "1x2",
          "market_name": "Match Result",
          "external_id": "offer_89234",
          "line": null,
          "selections": [
            { "key": "home", "name": "1", "odds": 1.72 },
            { "key": "draw", "name": "X", "odds": 3.50 },
            { "key": "away", "name": "2", "odds": 5.25 }
          ]
        }
      ]
    },
    {
      "category_key": "totales",
      "category_name": "Totales",
      "markets": [
        {
          "market_key": "over_under",
          "market_name": "Over/Under",
          "external_id": "offer_89235",
          "line": 2.5,
          "selections": [
            { "key": "over", "name": "Más de 2.5", "odds": 1.85 },
            { "key": "under", "name": "Menos de 2.5", "odds": 1.95 }
          ]
        },
        {
          "market_key": "over_under",
          "market_name": "Over/Under",
          "external_id": "offer_89236",
          "line": 3.5,
          "selections": [
            { "key": "over", "name": "Más de 3.5", "odds": 3.10 },
            { "key": "under", "name": "Menos de 3.5", "odds": 1.35 }
          ]
        }
      ]
    },
    {
      "category_key": "corners",
      "category_name": "Corners",
      "markets": [
        {
          "market_key": "total_corners",
          "market_name": "Corners - Over/Under",
          "external_id": "offer_89300",
          "line": 9.5,
          "selections": [
            { "key": "over", "name": "Más de 9.5", "odds": 1.90 },
            { "key": "under", "name": "Menos de 9.5", "odds": 1.90 }
          ]
        }
      ]
    }
  ]
}
```

> Nota: Un mercado con distintas líneas (ej. over/under 2.5, 3.5, 4.5) se representa como **múltiples documentos de `market`** dentro de la misma categoría, diferenciados por el campo `line`.

### 6.2 Colección `events` (índice de eventos normalizados)

```json
{
  "_id": "ObjectId",
  "normalized_key": "villarreal-cf_real-sociedad_20260320",
  "home_team": "Villarreal CF",
  "away_team": "Real Sociedad",
  "event_date": "2026-03-20T20:00:00Z",
  "competition_key": "la_liga",
  "sport": "football",
  "bookmaker_refs": {
    "speedy":     "1234567",
    "granmadrid": "9876",
    "kirol":      "456",
    "codere":     "codere_event_id"
  },
  "last_scraped": "2026-03-17T12:52:00Z"
}
```

Esta colección permite buscar eventos sin depender de un bookmaker específico.

### 6.3 Índices MongoDB recomendados

```javascript
// odds_snapshots
db.odds_snapshots.createIndex({ "bookmaker": 1, "event.normalized_key": 1, "scraped_at": -1 })
db.odds_snapshots.createIndex({ "event.normalized_key": 1, "scraped_at": -1 })
db.odds_snapshots.createIndex({ "competition.normalized_key": 1, "scraped_at": -1 })
db.odds_snapshots.createIndex({ "scraped_at": -1 }, { expireAfterSeconds: 2592000 }) // TTL 30 días

// events
db.events.createIndex({ "normalized_key": 1 }, { unique: true })
db.events.createIndex({ "competition_key": 1, "event_date": 1 })
```

---

## 7. Adaptadores de scraping a implementar

### 7.1 Puerto de scraping (sin cambios de interfaz)

```python
class BookmakerScraperPort(ABC):
    @abstractmethod
    async def scrape_markets(
        self,
        competition_key: str,
        bookmaker_cfg: BookmakerConfig,
        league_cfg: LeagueConfig,
    ) -> list[OddsSnapshot]: ...
```

Cambio respecto al actual: el adaptador recibe **objetos de configuración tipados** (del YAML) en lugar de parámetros ad-hoc.

### 7.2 `SpeedyScaper` (adapta `scrapers/speedy.py`)

- Extrae `group_id` de `league_cfg.bookmakers["speedy"].group_id`.
- Llama a la Kambi API con los parámetros del YAML.
- Por cada evento, normaliza los mercados usando `MarketNormalizer` con el `market_mappings` del YAML de SpeedyBet.
- Retorna `list[OddsSnapshot]`.
- Usa `BaseScraper.get_with_retry()` para todas las llamadas HTTP.

### 7.3 `GranMadridScraper` (adapta `scrapers/granmadrid.py`)

- Lee `champ_id`, `casino_url`, `token_wait_seconds` del YAML.
- Gestiona el ciclo de vida del `undetected_chromedriver` (iniciar, capturar token, cerrar) con `contextlib.contextmanager`.
- El token capturado se guarda en memoria durante la sesión (no persiste entre scrapes).
- Normaliza mercados via `MarketNormalizer`.
- **Consideración especial**: este scraper es el más frágil (depende de un navegador). Si falla la captura del token, lanza `TokenCaptureError(ScrapingError)` y el orquestador lo registra pero continúa con los demás scrapers.

### 7.4 `KirolScraper` (adapta `scrapers/kirol.py`)

- Lee `competition_id`, `base_url`, `request_delay` del YAML.
- Usa `BaseScraper.get_with_retry()` en lugar de `requests.get` directo.
- La fecha del evento se intenta parsear del HTML; si no se encuentra, queda `None`.
- Normaliza mercados via `MarketNormalizer`.

### 7.5 `BaseScraper` — clase base compartida

```python
class BaseScraper:
    def __init__(self, cfg: BookmakerConfig, logger: BoundLogger): ...

    def get_with_retry(
        self,
        url: str,
        params: dict = None,
        headers: dict = None,
    ) -> requests.Response:
        """HTTP GET con retry exponencial según config del bookmaker.
        Loggea cada intento y error con contexto estructurado."""
        ...

    def normalize_markets(
        self,
        raw_markets: list[dict],
        event: Event,
    ) -> list[MarketCategorySnapshot]:
        """Delega en MarketNormalizer con los market_mappings del YAML."""
        ...
```

---

## 8. Servicio de normalización de mercados

### 8.1 `app/domain/services/market_normalizer.py`

```python
class MarketNormalizer:
    """Convierte la lista cruda de mercados de un bookmaker
    en MarketCategorySnapshot canónicos del dominio."""

    def __init__(self, mappings: dict[str, MarketMapping], logger: BoundLogger): ...

    def normalize(
        self,
        raw_markets: list[dict],
        bookmaker: BookmakerName,
    ) -> list[MarketCategorySnapshot]:
        """
        1. Para cada mercado raw: busca en mappings por nombre exacto.
        2. Si no hay match exacto: intenta match parcial (contiene la clave).
        3. Si no hay match: clasifica en categoría "especiales".
        4. Agrupa las categorías.
        5. Normaliza selections: intenta mapear "1"→"home", "X"→"draw", "2"→"away",
           "Sí"→"yes", "No"→"no", "Más"→"over", "Menos"→"under".
        """
        ...
```

### 8.2 Mapeo de selecciones canónicas

```python
SELECTION_KEY_MAP = {
    # Resultado
    "1": "home", "local": "home", "home": "home",
    "x": "draw", "empate": "draw", "draw": "draw",
    "2": "away", "visitante": "away", "away": "away",
    # Totales
    "más": "over", "mas": "over", "over": "over", "+": "over",
    "menos": "under", "under": "under", "-": "under",
    # BTTS
    "sí": "yes", "si": "yes", "yes": "yes",
    "no": "no",
}
```

---

## 9. Adaptador MongoDB

### 9.1 `app/adapters/outbound/persistence/mongo_repository.py`

Implementa `OddsRepositoryPort`:

```python
class MongoOddsRepository(OddsRepositoryPort):
    def __init__(self, client: MongoClient, db_name: str, cfg: MongoConfig): ...

    async def save_snapshots(self, snapshots: list[OddsSnapshot]) -> None:
        """Inserta documentos en odds_snapshots y actualiza/upserta en events."""
        ...

    async def get_latest_odds(
        self,
        event_key: str,
        bookmakers: list[BookmakerName] | None = None,
        category_keys: list[str] | None = None,
    ) -> list[OddsSnapshot]:
        """Devuelve el snapshot más reciente por bookmaker para el event_key dado.
        Filtra opcionalmente por bookmakers y categorías de mercado."""
        ...

    async def get_odds_history(
        self,
        event_key: str,
        bookmaker: BookmakerName,
        since: datetime,
    ) -> list[OddsSnapshot]:
        """Historial de snapshots para un evento+bookmaker desde 'since'."""
        ...

    async def list_events(
        self,
        competition_key: str,
        from_date: datetime | None = None,
    ) -> list[Event]:
        """Lista eventos de la colección events por competición."""
        ...

    async def upsert_event(self, event: Event) -> None:
        """Upsert en la colección events por normalized_key."""
        ...
```

### 9.2 `app/infrastructure/database.py` — factory MongoDB

```python
def create_mongo_client(uri: str) -> MongoClient:
    """Crea cliente MongoDB con timeouts configurados."""
    return MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )

def get_mongo_db(client: MongoClient, db_name: str) -> Database:
    return client[db_name]
```

---

## 10. Manejo de errores

### 10.1 Jerarquía de excepciones de dominio: `app/domain/exceptions.py`

```python
class SportsbookError(Exception):
    """Base de todas las excepciones de dominio."""
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.context = context or {}

# Scraping
class ScrapingError(SportsbookError): ...
class TokenCaptureError(ScrapingError): ...      # GranMadrid: fallo al capturar token
class EventsNotFoundError(ScrapingError): ...    # La API no devuelve eventos
class MarketParseError(ScrapingError): ...       # Error parseando un mercado individual

# Persistencia
class RepositoryError(SportsbookError): ...
class ConnectionError(RepositoryError): ...
class DocumentNotFoundError(RepositoryError): ...

# Configuración
class ConfigurationError(SportsbookError): ...
class MissingConfigError(ConfigurationError): ...  # Falta campo obligatorio en YAML
class InvalidConfigError(ConfigurationError): ...  # Valor inválido en YAML

# Normalización
class NormalizationError(SportsbookError): ...
```

### 10.2 Estrategia de manejo en el orquestador

```python
# En ScrapingUseCase.run()
for bookmaker_name, scraper in scrapers.items():
    try:
        snapshots = await scraper.scrape_markets(competition_key, ...)
        await repository.save_snapshots(snapshots)
        logger.info("scrape_completed", bookmaker=bookmaker_name, count=len(snapshots))
    except TokenCaptureError as e:
        logger.warning("token_capture_failed", bookmaker=bookmaker_name, error=str(e))
        # Continúa con el siguiente bookmaker
    except EventsNotFoundError as e:
        logger.warning("no_events_found", bookmaker=bookmaker_name, **e.context)
    except ScrapingError as e:
        logger.error("scrape_failed", bookmaker=bookmaker_name, error=str(e), **e.context)
    except RepositoryError as e:
        logger.error("save_failed", bookmaker=bookmaker_name, error=str(e))
```

---

## 11. Logging estructurado

### 11.1 Configuración en `app/infrastructure/logging_config.py`

Ampliar la configuración actual de `structlog` para añadir:

- **Contexto de bookmaker y evento** vinculado via `structlog.contextvars.bind_contextvars()`.
- **Nivel configurable** desde `config/app.yaml`.
- **Salida a fichero** si se configura `logging.output: file`.

```python
def configure_logging(level: str = "INFO", fmt: str = "json", output: str = "stdout", file_path: str = None):
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(processors=processors, ...)
```

### 11.2 Eventos de log estandarizados

| Evento (`event`) | Nivel | Campos adicionales |
|---|---|---|
| `scrape_started` | INFO | `bookmaker`, `competition_key`, `league_name` |
| `events_fetched` | INFO | `bookmaker`, `count` |
| `event_scraped` | DEBUG | `bookmaker`, `event_key`, `market_count` |
| `event_scrape_failed` | WARNING | `bookmaker`, `event_key`, `error` |
| `scrape_completed` | INFO | `bookmaker`, `event_count`, `duration_ms` |
| `scrape_failed` | ERROR | `bookmaker`, `error`, `traceback` |
| `token_capture_failed` | WARNING | `bookmaker` |
| `normalization_fallback` | DEBUG | `bookmaker`, `raw_name`, `fallback_category` |
| `snapshot_saved` | DEBUG | `bookmaker`, `event_key`, `snapshot_id` |
| `mongo_connection_error` | ERROR | `uri_prefix`, `error` |
| `cache_miss` | DEBUG | `key` |
| `cache_hit` | DEBUG | `key` |
| `daily_job_skipped` | INFO | `date`, `reason` |
| `daily_job_started` | INFO | `date` |
| `daily_job_completed` | INFO | `date`, `bookmakers_ok`, `bookmakers_failed` |

---

## 12. Cambios en la API REST

### 12.1 Endpoints afectados

**Nuevos parámetros en `GET /odds`:**

```
GET /api/v1/odds
  ?event_key=villarreal-cf_real-sociedad_20260320   # normalized_key
  &bookmakers=speedy,granmadrid,kirol               # filtro por bookmakers
  &categories=resultado,totales                     # filtro por categorías de mercado
  &market_key=1x2                                   # filtro por submercado específico
```

**Nuevo endpoint `GET /compare/{event_key}`:**

```json
{
  "event_key": "villarreal-cf_real-sociedad_20260320",
  "event_date": "2026-03-20T20:00:00Z",
  "comparison": {
    "resultado": {
      "1x2": {
        "market_name": "1X2 / Match Result",
        "bookmakers": {
          "speedy":     { "home": 1.72, "draw": 3.50, "away": 5.25 },
          "granmadrid": { "home": 1.70, "draw": 3.55, "away": 5.40 },
          "kirol":      { "home": 1.75, "draw": 3.45, "away": 5.10 }
        },
        "best_odds": { "home": "kirol", "draw": "granmadrid", "away": "granmadrid" }
      }
    },
    "totales": {
      "over_under": {
        "market_name": "Over/Under",
        "lines": {
          "2.5": {
            "bookmakers": {
              "speedy":     { "over": 1.85, "under": 1.95 },
              "granmadrid": { "over": 1.87, "under": 1.93 }
            }
          }
        }
      }
    }
  }
}
```

**Nuevo endpoint `GET /bookmakers` — añadir estado:**

```json
[
  { "key": "speedy",     "name": "SpeedyBet",          "enabled": true,  "last_scrape": "2026-03-17T12:51:17Z" },
  { "key": "granmadrid", "name": "Casino Gran Madrid",  "enabled": true,  "last_scrape": "2026-03-17T12:51:53Z" },
  { "key": "kirol",      "name": "Kirolbet",            "enabled": true,  "last_scrape": "2026-03-17T12:52:27Z" },
  { "key": "codere",     "name": "Codere",              "enabled": true,  "last_scrape": null }
]
```

**Nuevo endpoint `GET /leagues/{league_key}/categories`:**

```json
{
  "league_key": "la_liga",
  "categories_by_bookmaker": {
    "speedy":     ["resultado", "totales", "handicap", "ambos_marcan", "corners", "mitad"],
    "granmadrid": ["resultado", "totales", "handicap", "especiales"],
    "kirol":      ["resultado", "totales", "marcador_exacto", "ambos_marcan"]
  }
}
```

---

## 13. Dependencias nuevas a añadir

```
# requirements.txt — añadir:
motor>=3.3.0                    # driver MongoDB async (compatible con asyncio)
pymongo>=4.6.0                  # cliente MongoDB sync (para scripts CLI)
pyyaml>=6.0.1                   # carga de config YAML
undetected-chromedriver>=3.5.5  # GranMadrid (ya en uso en scrapers/, formalizar)
beautifulsoup4>=4.12.0          # Kirolbet (ya en uso, formalizar)
lxml>=5.1.0                     # parser HTML alternativo para BS4
```

> `motor` es el driver async de MongoDB recomendado para usar con FastAPI/asyncio. `pymongo` se mantiene para los scripts CLI (`main.py`, `scripts/`).

---

## 14. Variables de entorno (`.env`)

Añadir a `.env.example`:

```dotenv
# MongoDB
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/
MONGO_DB_NAME=sportsbook_scraper

# Config paths (override para distintos entornos)
APP_CONFIG_PATH=config/app.yaml
LEAGUES_CONFIG_PATH=config/leagues.yaml
BOOKMAKERS_CONFIG_DIR=config/bookmakers/
```

---

## 15. Plan de implementación

### Fase 1 — Dominio y configuración (sin romper nada existente)
1. Crear `app/domain/exceptions.py` con la jerarquía de excepciones.
2. Ampliar `BookmakerName` con `SPEEDY`, `GRANMADRID`, `KIROL`.
3. Refactorizar `app/domain/models/market.py`: nuevas clases `MarketCategory`, `Market`, `Selection`, `MarketCategorySnapshot`, `OddsSnapshot` actualizado.
4. Añadir campo `normalized_key` a `Event`.
5. Crear `app/domain/models/competition.py`.
6. Implementar `app/infrastructure/config_loader.py` + Pydantic models para YAML.
7. Crear los archivos YAML en `config/`.

### Fase 2 — Normalización de mercados
8. Implementar `app/domain/services/market_normalizer.py`.
9. Implementar `app/adapters/outbound/scrapers/base_scraper.py`.
10. Tests unitarios del normalizador con datos reales de los 3 scrapers.

### Fase 3 — Scrapers hexagonales
11. Implementar `SpeedyScraper`, `GranMadridScraper`, `KirolScraper`.
12. Mantener `scrapers/` (CLI standalone) operativos; **no eliminarlos** hasta validar la integración.
13. Tests de integración con fixtures de los JSON actuales en `data/`.

### Fase 4 — Persistencia MongoDB
14. Implementar `MongoOddsRepository`.
15. Actualizar `app/infrastructure/database.py` con factory MongoDB.
16. Actualizar `app/adapters/inbound/api/dependencies.py` para inyectar MongoDB.
17. Crear colecciones e índices en MongoDB.
18. Tests de integración del repositorio con MongoDB local (docker-compose).

### Fase 5 — API y logging
19. Actualizar endpoints `/odds`, `/compare`, `/bookmakers` con el nuevo modelo.
20. Añadir endpoint `GET /leagues/{key}/categories`.
21. Ampliar `logging_config.py` con los nuevos campos y eventos.
22. Propagar `bind_contextvars` en scrapers y repositorio.

### Fase 6 — Validación y cleanup
23. Tests end-to-end con datos reales.
24. Deprecar `supabase_repository.py` (mantener en rama, no eliminar).
25. Actualizar `scripts/run_laliga_daily_job.py` para usar los nuevos scrapers.
26. Documentar con OpenAPI actualizado.

---

## 16. Decisiones de diseño y justificaciones

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| MongoDB como persistencia principal | Mantener Supabase (PostgreSQL) | Los mercados son estructuralmente heterogéneos: distintas casas tienen distintas categorías y líneas. Un esquema fijo de tablas requeriría columnas nullable masivas o EAV, lo que dificulta las consultas. Un documento JSON anidado es más natural y performante para este caso. |
| Config en YAML, secretos en .env | Todo en .env o todo en YAML | Los secretos (credenciales) no deben versionarse; la configuración estructural (mappings, IDs, parámetros) sí. |
| `motor` para MongoDB async | `pymongo` directo en endpoints | FastAPI es async; bloquear el event loop con pymongo sync degrada el rendimiento. |
| Normalización de mercados en capa de dominio | Normalizar en el adaptador | La lógica de negocio (qué es un mercado de "resultado" vs "total") pertenece al dominio, no a la infraestructura. |
| Mantener scrapers CLI en `scrapers/` durante la migración | Eliminarlos desde el inicio | Permiten validar el comportamiento de los nuevos adaptadores comparando output. |
| `normalized_key` para cruzar eventos entre casas | ID compartido entre casas | No existe un ID universal entre casas; el slug equipo+fecha es determinista y reproducible. |
| Clase base `BaseScraper` | Mixins o funciones libres | Centraliza retry, headers y logging, evitando duplicación entre los 4 scrapers. |
