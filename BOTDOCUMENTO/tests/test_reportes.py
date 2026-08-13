from unittest.mock import patch

from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health_check():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "cobalto-reportes"

def test_analizar_ia_sin_novedades():
    resp = client.post("/api/reportes/analizar-ia", json={"novedades": []})
    assert resp.status_code == 422
    assert "novedad" in resp.json()["detail"].lower()

def test_analizar_ia_texto_vacio():
    resp = client.post(
        "/api/reportes/analizar-ia",
        json={
            "novedades": [
                {
                    "fecha_situacion": "17JUN2026",
                    "portal_web_url": "https://example.com",
                    "texto_situacion": "   ",
                    "imagenes": [],
                }
            ]
        },
    )
    assert resp.status_code == 422

@patch("backend.routers.reportes.obtener_analisis_ia")
def test_analizar_ia_exitoso(mock_obtener):
    mock_obtener.return_value = {"actores": ["Test"], "amenaza": "Media", "analisis": "Análisis simulado."}

    resp = client.post(
        "/api/reportes/analizar-ia",
        json={
            "novedades": [
                {
                    "fecha_situacion": "17JUN2026",
                    "portal_web_url": "https://example.com",
                    "texto_situacion": "Novedad de prueba para el endpoint.",
                    "imagenes": [],
                }
            ]
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["actores"] == ["Test"]

@patch("backend.routers.reportes.obtener_analisis_ia")
def test_analizar_ia_error(mock_obtener):
    from backend.services.groq_service import GroqAnalysisError
    mock_obtener.side_effect = GroqAnalysisError("Error simulado de Groq.")
    resp = client.post(
        "/api/reportes/analizar-ia",
        json={
            "novedades": [
                {
                    "fecha_situacion": "17JUN2026",
                    "portal_web_url": "https://example.com",
                    "texto_situacion": "Texto que provocará error.",
                    "imagenes": [],
                }
            ]
        },
    )
    assert resp.status_code == 504

def test_generar_word_exitoso():
    resp = client.post(
        "/api/reportes/generar-word",
        json={
            "novedades": [
                {
                    "fecha_situacion": "17JUN2026",
                    "portal_web_url": "https://example.com",
                    "texto_situacion": "Novedad de prueba para el endpoint.",
                    "imagenes": [],
                }
            ],
            "analisis_por_novedad": [
                {"actores": ["Test"], "amenaza": "Media", "analisis": "Análisis simulado."}
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

def test_generar_word_mismatch():
    resp = client.post(
        "/api/reportes/generar-word",
        json={
            "novedades": [
                {
                    "fecha_situacion": "17JUN2026",
                    "portal_web_url": "https://example.com",
                    "texto_situacion": "Novedad de prueba para el endpoint.",
                    "imagenes": [],
                }
            ],
            "analisis_por_novedad": []
        },
    )
    assert resp.status_code == 422
