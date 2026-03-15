"""Tests de integración de la API (endpoints)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_bookmakers_list(client: TestClient):
    r = client.get("/api/v1/bookmakers")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(b["slug"] == "codere" for b in data)


def test_odds_empty(client: TestClient):
    r = client.get("/api/v1/odds")
    assert r.status_code == 200
    assert r.json() == []


def test_scrape_status(client: TestClient):
    r = client.get("/api/v1/scrape/status")
    assert r.status_code == 200
    assert "status" in r.json()


def test_laliga_hoy_endpoint_exists(client: TestClient):
    """Verifica que el endpoint existe. Con repo en memoria devuelve 200 con 0 cuotas."""
    r = client.post("/api/v1/scrape/laliga-hoy?bookmaker=fake")
    # bookmaker inexistente -> 0 cuotas pero respuesta válida
    assert r.status_code == 200
    data = r.json()
    assert "total_cuotas_insertadas" in data
    assert "partidos_scrapeados" in data
    assert "detalle" in data
    assert data["total_cuotas_insertadas"] == 0
