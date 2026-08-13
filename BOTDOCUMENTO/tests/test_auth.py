from unittest.mock import patch

from backend.config import settings

# Test 1: Auth disabled by default
from backend.main import app as app_noauth
from fastapi.testclient import TestClient

client_noauth = TestClient(app_noauth)


def test_health_sin_auth():
    resp = client_noauth.get("/api/health")
    assert resp.status_code == 200


def test_osint_sin_auth():
    resp = client_noauth.get("/api/osint/entries")
    assert resp.status_code == 200


# Test 2: Auth enabled — rebuild app via create_app()
AUTH_SETTINGS = {"auth_enabled": True, "auth_token": "test-token-456"}


def _build_auth_app():
    with patch.multiple(settings, **AUTH_SETTINGS):
        from backend.main import create_app
        return create_app()


client_auth = TestClient(_build_auth_app())


def test_health_con_auth():
    resp = client_auth.get("/api/health")
    assert resp.status_code == 200


def test_osint_sin_token():
    resp = client_auth.get("/api/osint/entries")
    assert resp.status_code == 401


def test_osint_token_valido():
    resp = client_auth.get(
        "/api/osint/entries", headers={"Authorization": "Bearer test-token-456"}
    )
    assert resp.status_code == 200


def test_osint_token_invalido():
    resp = client_auth.get(
        "/api/osint/entries", headers={"Authorization": "Bearer wrong-token"}
    )
    assert resp.status_code == 401


def test_osint_scheme_invalido():
    resp = client_auth.get(
        "/api/osint/entries", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert resp.status_code == 401


def test_reporte_token_valido():
    resp = client_auth.post(
        "/api/reportes/generar-word",
        json={
            "novedades": [
                {
                    "fecha_situacion": "test",
                    "portal_web_url": "https://x.com",
                    "texto_situacion": "test test test",
                    "imagenes": [],
                }
            ],
            "analisis_por_novedad": [
                {"actores": ["Test"], "amenaza": "Media", "analisis": "Análisis"}
            ]
        },
        headers={"Authorization": "Bearer test-token-456"},
    )
    assert resp.status_code == 200
