"""
tests/test_osiris_bridge.py
Tests de integración para los endpoints del OSIRIS bridge.
Valida estructura de respuestas, rate limiting y lógica interna sin llamadas reales a APIs externas.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Tests de módulos internos OSIRIS (sin HTTP) ──

def test_osiris_bridge_imports():
    """El módulo osiris_bridge debe importar sin errores."""
    import osiris_bridge
    assert hasattr(osiris_bridge, "router")
    assert osiris_bridge.router.prefix == "/api/osiris"


def test_osiris_bridge_rate_limiter():
    """El rate limiter debe aceptar IPs nuevas y rechazar IPs que superan el límite."""
    from osiris_bridge import _check_rate_limit, _rate_limit_map, _RATE_MAX

    test_ip = "10.0.0.254"  # IP de test que no se usará en producción
    # Limpiar estado previo si existe
    _rate_limit_map.pop(test_ip, None)

    # Las primeras _RATE_MAX peticiones deben pasar
    for i in range(_RATE_MAX):
        result = _check_rate_limit(test_ip)
        assert result is True, f"Debería pasar en intento {i+1}"

    # La siguiente debe ser rechazada
    result = _check_rate_limit(test_ip)
    assert result is False, "Debería ser rechazada por rate limit"

    # Limpiar
    _rate_limit_map.pop(test_ip, None)


def test_osiris_bridge_rate_limiter_different_ips():
    """El rate limiter es por IP — IPs distintas tienen límites independientes."""
    from osiris_bridge import _check_rate_limit, _rate_limit_map

    ip_a = "10.0.1.1"
    ip_b = "10.0.1.2"
    _rate_limit_map.pop(ip_a, None)
    _rate_limit_map.pop(ip_b, None)

    assert _check_rate_limit(ip_a) is True
    assert _check_rate_limit(ip_b) is True

    _rate_limit_map.pop(ip_a, None)
    _rate_limit_map.pop(ip_b, None)


def test_osiris_bridge_router_routes():
    """El router OSIRIS debe tener las rutas críticas registradas."""
    import osiris_bridge
    routes = [r.path for r in osiris_bridge.router.routes]

    expected_routes = [
        "/api/osiris/health",
        "/api/osiris/recon/dns",
        "/api/osiris/recon/whois",
        "/api/osiris/recon/ip",
        "/api/osiris/sanctions",
        "/api/osiris/data/flights",
        "/api/osiris/data/satellites",
        "/api/osiris/data/earthquakes",
        "/api/osiris/data/fires",
        "/api/osiris/data/cctv",
        "/api/osiris/cctv/image",
        "/api/osiris/data/crypto",
        "/api/osiris/data/markets",
        "/api/osiris/data/weather",
        "/api/osiris/data/malware",
        "/api/osiris/data/cyber-threats",
    ]
    for route in expected_routes:
        assert route in routes, f"Ruta faltante: {route}"


def test_osiris_bridge_router_count():
    """El router debe tener al menos 30 endpoints registrados."""
    import osiris_bridge
    routes = osiris_bridge.router.routes
    assert len(routes) >= 30, f"Solo {len(routes)} rutas registradas — se esperaban ≥30"


# ── Tests con cliente HTTP in-process ──

def _make_osiris_client():
    """Crea un AsyncClient con el router OSIRIS montado en una mini-app test."""
    import httpx
    from fastapi import FastAPI
    import osiris_bridge

    test_app = FastAPI()
    test_app.include_router(osiris_bridge.router)
    return httpx.AsyncClient(app=test_app, base_url="http://test")


@pytest.mark.asyncio
async def test_osiris_health_response():
    """GET /api/osiris/health debe retornar status ok con campos requeridos."""
    async with _make_osiris_client() as client:
        resp = await client.get("/api/osiris/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["platform"] == "OSIRIS-on-COBALTO"
        assert "timestamp" in data
        assert "version" in data


@pytest.mark.asyncio
async def test_osiris_recon_dns_missing_param():
    """GET /api/osiris/recon/dns sin parámetro debe retornar 422."""
    async with _make_osiris_client() as client:
        resp = await client.get("/api/osiris/recon/dns")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_osiris_recon_ip_missing_param():
    """GET /api/osiris/recon/ip sin parámetro debe retornar 422."""
    async with _make_osiris_client() as client:
        resp = await client.get("/api/osiris/recon/ip")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_osiris_sanctions_short_query():
    """GET /api/osiris/sanctions con query < 2 chars debe retornar 422."""
    async with _make_osiris_client() as client:
        resp = await client.get("/api/osiris/sanctions?query=a")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_osiris_rate_limit_enforcement():
    """El rate limiter debe retornar 429 tras superar el límite."""
    import time
    from osiris_bridge import _rate_limit_map, _RATE_MAX

    fake_ip = "192.0.2.99"  # TEST-NET-1, no enrutado en internet real
    now = time.time()
    _rate_limit_map[fake_ip] = [now] * _RATE_MAX

    async with _make_osiris_client() as client:
        resp = await client.get(
            "/api/osiris/recon/dns?domain=example.com",
            headers={"X-Forwarded-For": fake_ip},
        )
        assert resp.status_code == 429
        data = resp.json()
        assert "error" in data

    _rate_limit_map.pop(fake_ip, None)
