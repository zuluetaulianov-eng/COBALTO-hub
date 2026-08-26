"""
test_colombia_recon.py - Tests unitarios e integración para la suite OSINT Colombia
(SECOP II, JEP, Rama Judicial y SQLite local).
"""
from unittest.mock import MagicMock, patch

import pytest

from osiris_colombia_recon import (
    _save_secop_records_to_db,
    get_colombia_intel_summary,
    init_colombia_db,
    load_rama_judicial_cookies,
    query_rama_judicial_radicado,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_colombia_db()

def test_db_initialization_and_insertion():
    sample_records = [{
        "urlproceso": {"url": "https://www.datos.gov.co/test_contract_123"},
        "fecha_de_firma": "2026-08-26",
        "nombre_del_contratista": "CONTRATISTA DE PRUEBA SAS",
        "nombre_entidad": "MINISTERIO DE DEFENSA",
        "valor_del_contrato": "150000000",
        "descripcion_del_proceso": "Mantenimiento táctico de equipos de radar"
    }]
    _save_secop_records_to_db(sample_records)
    summary = get_colombia_intel_summary(limit=10)
    assert len(summary) >= 1
    found = any(r["fuente_origen"] == "SECOP_II" for r in summary)
    assert found is True

@pytest.mark.asyncio
async def test_query_rama_judicial_invalid_length():
    res = await query_rama_judicial_radicado("12345")
    assert "error" in res
    assert "23 dígitos" in res["error"]

def test_load_cookies_non_existent():
    cookies = load_rama_judicial_cookies()
    assert isinstance(cookies, dict)
