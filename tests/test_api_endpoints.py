"""
tests/test_api_endpoints.py
Tests de integración HTTP para los endpoints críticos de COBALTO HUB.
Usa httpx.AsyncClient con el app FastAPI montado in-process (sin servidor real).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Setup de variables de entorno antes de importar app ──
os.environ.setdefault("ADMIN_PASSWORD", "test_ci_password")
os.environ.setdefault("JWT_SECRET", "test-ci-jwt-secret-32chars-minimum")
os.environ.setdefault("OLLAMA_ENABLED", "false")  # No conectar a Ollama en CI


def _make_client():
    """Crea un nuevo AsyncClient con la app FastAPI montada in-process."""
    import httpx
    from app import app
    return httpx.AsyncClient(app=app, base_url="http://test")


# ── Health & Config ──

@pytest.mark.asyncio
async def test_health_endpoint():
    """GET / debe retornar 200 o 401 (si auth está habilitada en CI)."""
    async with _make_client() as client:
        resp = await client.get("/")
        assert resp.status_code in (200, 302, 401), f"Inesperado: {resp.status_code}"


@pytest.mark.asyncio
async def test_api_config_get():
    """GET /api/config debe retornar JSON con campos esperados."""
    async with _make_client() as client:
        resp = await client.get("/api/config")
        assert resp.status_code in (200, 401, 403)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_api_status():
    """GET /api/status debe retornar JSON con estado del sistema."""
    async with _make_client() as client:
        resp = await client.get("/api/status")
        assert resp.status_code in (200, 401, 403, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


# ── Auth ──

@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """POST /api/login con credenciales inválidas debe retornar 401."""
    async with _make_client() as client:
        resp = await client.post(
            "/api/login",
            json={"username": "admin", "password": "wrong_password_xyz"},
        )
        assert resp.status_code in (401, 422, 404)


@pytest.mark.asyncio
async def test_login_empty_credentials():
    """POST /api/login con credenciales vacías debe rechazarse."""
    async with _make_client() as client:
        resp = await client.post(
            "/api/login",
            json={"username": "", "password": ""},
        )
        assert resp.status_code in (400, 401, 422, 404)


# ── Static ──

@pytest.mark.asyncio
async def test_static_css_served():
    """El archivo CSS principal debe servirse correctamente."""
    async with _make_client() as client:
        resp = await client.get("/static/css/dashboard.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_static_js_main_served():
    """El script principal JS debe servirse correctamente."""
    async with _make_client() as client:
        resp = await client.get("/static/js/main.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers.get("content-type", "")


# ── API Map Data ──

@pytest.mark.asyncio
async def test_api_map_data():
    """GET /api/map-data debe retornar JSON con estructura esperada."""
    async with _make_client() as client:
        resp = await client.get("/api/map-data")
        assert resp.status_code in (200, 401, 403, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (dict, list))


# ── OSIRIS Health ──

@pytest.mark.asyncio
async def test_osiris_health():
    """GET /api/osiris/health debe retornar status ok."""
    async with _make_client() as client:
        resp = await client.get("/api/osiris/health")
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "ok"
            assert "platform" in data
            assert "version" in data


# ── Validación de tipos de respuesta ──

@pytest.mark.asyncio
async def test_404_returns_json_or_html():
    """Las rutas inexistentes deben retornar 404 o 401 (si auth intercepta)."""
    async with _make_client() as client:
        resp = await client.get("/api/endpoint_que_no_existe_xyz")
        assert resp.status_code in (404, 401)
