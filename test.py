import requests
BASE_URL = "https://m.apuestas.codere.es/NavigationService"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://m.apuestas.codere.es/",
}
def get_sports():
    """Paso 1: Obtener todos los deportes"""
    r = requests.get(f"{BASE_URL}/Home/GetSports", headers=HEADERS)
    return r.json()
def get_leagues(sport_handle, sport_node_id):
    """Paso 2: Obtener ligas de un deporte"""
    r = requests.get(
        f"{BASE_URL}/Home/GetCountriesByDate",
        params={"sportHandle": sport_handle, "nodeId": sport_node_id},
        headers=HEADERS
    )
    countries = r.json()
    leagues = []
    for country in countries:
        for league in country.get("Leagues", []):
            leagues.append(league)
    return leagues
def get_events(league_node_id, day_offset=0):
    """Paso 3: Obtener partidos de una liga"""
    r = requests.get(
        f"{BASE_URL}/Event/GetMultipleEventsByDate",
        params={
            "utcOffsetHours": 1,
            "dayDifference": day_offset,
            "parentids": league_node_id,
            "gametypes": "1;18"
        },
        headers=HEADERS
    )
    data = r.json()
    return data.get(str(league_node_id), [])
def get_categories(event_node_id):
    """Paso 4: Obtener categorías de mercados de un partido"""
    r = requests.get(
        f"{BASE_URL}/Game/GetGamesNoLiveAndCategoryInfos",
        params={"parentid": event_node_id},
        headers=HEADERS
    )
    return r.json().get("CategoriesInformation", [])
def get_markets(event_node_id, category_id):
    """Paso 5: Obtener mercados de una categoría"""
    r = requests.get(
        f"{BASE_URL}/Game/GetGamesNoLiveByCategoryInfo",
        params={"parentid": event_node_id, "categoryInfoId": category_id},
        headers=HEADERS
    )
    return r.json()
def scrape_faltas(league_name="Primera División", sport_handle="soccer"):
    # 1. Obtener deporte
    sports = get_sports()
    sport = next(s for s in sports if s["SportHandle"] == sport_handle)
    # 2. Obtener liga por nombre
    leagues = get_leagues(sport_handle, sport["NodeId"])
    league = next(l for l in leagues if league_name.lower() in l["Name"].lower())
    print(f"Liga: {league['Name']} (NodeId: {league['NodeId']})")
    # 3. Obtener partidos
    events = get_events(league["NodeId"])
    print(f"Partidos encontrados: {len(events)}")
    results = []
    for event in events:
        home = event["Participants"][0]["LocalizedNames"]["LocalizedValues"][0]["Value"]
        away = event["Participants"][1]["LocalizedNames"]["LocalizedValues"][0]["Value"]
        event_id = event["NodeId"]
        # 4. Obtener categorías y buscar ESTADÍSTICAS dinámicamente
        categories = get_categories(event_id)
        estadisticas = next(
            (c for c in categories if "ESTAD" in c["CategoryName"].upper()),
            None
        )
        if not estadisticas:
            continue
        # 5. Obtener mercados de faltas
        markets = get_markets(event_id, estadisticas["CategoryId"])
        faltas = [m for m in markets if "falt" in m.get("Name", "").lower()]
        for mercado in faltas:
            cuotas = {r["Name"]: r["Odd"] for r in mercado.get("Results", [])}
            results.append({
                "partido": f"{home} vs {away}",
                "mercado": mercado["Name"],
                "cuotas": cuotas
            })
    return results
# Ejecutar
for r in scrape_faltas("Premier League"):
    print(f"\\n{r['partido']} | {r['mercado']}")
    for nombre, cuota in r['cuotas'].items():
        print(f"  {nombre}: {cuota}")