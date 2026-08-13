"""Tests for HUMINT module (FASE 5)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from humint_bot import (
    LAT_LON_RE,
    get_report,
    get_reports,
    get_stats,
    parse_telegram_message,
    store_report,
    update_status,
)


def test_store_and_retrieve():
    rid = store_report(
        source="test",
        reporter="agent_001",
        latitude=10.4806,
        longitude=-66.9036,
        title="Test report",
        description="Test HUMINT",
        severity="high",
        tags=["test", "caracas"],
    )
    assert rid is not None
    assert len(rid) == 12

    r = get_report(rid)
    assert r is not None
    assert r["title"] == "Test report"
    assert r["reporter"] == "agent_001"
    assert r["latitude"] == 10.4806
    assert r["longitude"] == -66.9036
    assert r["severity"] == "high"


def test_get_reports():
    store_report(title="Report A", severity="info")
    store_report(title="Report B", severity="critical")
    all_reports = get_reports(limit=10)
    assert len(all_reports) >= 2

    critical = get_reports(limit=10, severity="critical")
    assert all(r["severity"] == "critical" for r in critical)


def test_get_reports_empty():
    empty = get_reports(limit=10, status="nonexistent")
    assert len(empty) == 0


def test_update_status():
    rid = store_report(title="Status test")
    assert update_status(rid, "reviewed") is True
    r = get_report(rid)
    assert r["status"] == "reviewed"

    assert update_status("nonexistent", "reviewed") is False


def test_get_stats():
    store_report(title="Stats A", severity="info")
    store_report(title="Stats B", severity="info")
    stats = get_stats()
    assert stats["total"] >= 2
    assert "info" in stats["by_severity"]
    assert stats["by_severity"]["info"] >= 2
    assert "new" in stats["by_status"]


def test_parse_coordinates():
    parsed = parse_telegram_message("10.4806, -66.9036 — Evento reportado")
    assert parsed["latitude"] == 10.4806
    assert parsed["longitude"] == -66.9036

    parsed = parse_telegram_message("Coords: 40.7128 / -74.0060")
    assert parsed["latitude"] == 40.7128
    assert parsed["longitude"] == -74.0060

    parsed = parse_telegram_message("Sin coordenadas")
    assert parsed["latitude"] is None
    assert parsed["longitude"] is None


def test_parse_severity():
    parsed = parse_telegram_message("CRÍTICO: explosión detectada")
    assert parsed["severity"] == "critical"

    parsed = parse_telegram_message("Alto riesgo en la zona")
    assert parsed["severity"] == "high"

    parsed = parse_telegram_message("Medio movimiento sospechoso")
    assert parsed["severity"] == "medium"

    parsed = parse_telegram_message("Reporte rutinario")
    assert parsed["severity"] == "info"


def test_parse_title():
    parsed = parse_telegram_message("Título del reporte\nMás detalles aquí")
    assert parsed["title"] == "Título del reporte"
    assert parsed["severity"] == "info"


def test_lat_lon_regex():
    assert LAT_LON_RE.search("10.4806, -66.9036") is not None
    assert LAT_LON_RE.search("-33.45, -70.67") is not None
    assert LAT_LON_RE.search("51.5074; 0.1278") is not None
    assert LAT_LON_RE.search("51.5074 / 0.1278") is not None
    assert LAT_LON_RE.search("Sin números") is None
