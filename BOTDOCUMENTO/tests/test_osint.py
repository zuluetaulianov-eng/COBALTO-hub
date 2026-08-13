from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_listar_tags():
    resp = client.get("/api/osint/tags")
    assert resp.status_code == 200
    assert "CIBERSEGURIDAD" in resp.json()
    assert "GEOPOLÍTICA" in resp.json()
    assert "FINANCIERO" in resp.json()


def test_listar_entries_sin_filtros():
    resp = client.get("/api/osint/entries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3
    assert len(body["data"]) <= 10
    assert "data" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body


def test_filtrar_por_tag():
    resp = client.get("/api/osint/entries?tag=CIBERSEGURIDAD")
    assert resp.status_code == 200
    body = resp.json()
    assert all(e["tag"] == "CIBERSEGURIDAD" for e in body["data"])
    assert body["total"] > 0


def test_buscar_por_texto():
    resp = client.get("/api/osint/entries?q=phishing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


def test_paginacion():
    resp = client.get("/api/osint/entries?limit=1&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["limit"] == 1
    assert body["offset"] == 0


def test_limit_maximo():
    resp = client.get("/api/osint/entries?limit=100")
    assert resp.status_code == 422


def test_tag_inexistente():
    resp = client.get("/api/osint/entries?tag=INEXISTENTE")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_entry_tiene_campos_esperados():
    resp = client.get("/api/osint/entries?limit=1")
    entry = resp.json()["data"][0]
    for campo in ("id", "tag", "titulo", "fecha", "urlPortal", "textoSituacion"):
        assert campo in entry
