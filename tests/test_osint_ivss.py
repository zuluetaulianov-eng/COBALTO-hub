import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from osint_ivss import (
    _classify,
    get_ivss_data,
    ivss_lookup,
    validate_cedula,
)


def test_validate_cedula_valid_national():
    res = validate_cedula("V-1234567")
    assert res["valida"] is True
    assert res["nacionalidad"] == "V"
    assert res["solo_validacion_estructural"] is True
    # Estructural only: no personal data is fabricated
    assert "nombre" not in res
    assert "patrono" not in res


def test_validate_cedula_valid_extranjero():
    res = validate_cedula("E-12345678")
    assert res["valida"] is True
    assert res["nacionalidad"] == "E"


def test_validate_cedula_invalid_empty():
    res = validate_cedula("")
    assert res["valida"] is False


def test_validate_cedula_invalid_letter():
    res = validate_cedula("X-1234567")
    assert res["valida"] is False


def test_classify_pensiones():
    assert _classify("Pago de pensiones correspondiente al mes de abril") == "pensiones_pagos"


def test_classify_salud():
    assert _classify("Entrega de medicamentos de alto costo a pacientes oncológicos") == "salud"


def test_classify_tramites():
    assert _classify("Registro de empleadores en el sistema de autoliquidación") == "tramites_servicios"


def test_classify_institucional():
    assert _classify("Comandante Hugo Chávez presente en el corazón de los trabajadores") == "institucional"


def test_ivss_lookup_no_individual_profiling():
    """Ensure the institutional lookup never fabricates personal data."""
    res = ivss_lookup("V-12345678")
    assert res["alcance"] == "OSINT institucional público — sin perfilamiento de personas naturales"
    # The cédula is only structurally validated, never turned into a personal record
    doc = res["documento_consultado"]
    assert doc["validacion_formato"]["valida"] is True
    assert "no se consulta" in doc["nota"]
    assert res["status"] in ("CONSULTADO", "DEGRADADO", "SIN_DATOS")


def test_ivss_lookup_structure():
    res = ivss_lookup()
    assert "institucion" in res
    assert "comunicados" in res
    assert "pensiones_y_pagos" in res
    assert "alertas_salud" in res
    assert "tramites_y_servicios" in res
    assert "fuente" in res


def test_get_ivss_data_structure():
    data = get_ivss_data()
    assert "timestamp" in data
    assert "sources" in data
    assert "count" in data
    assert "🇻🇪 IVSS Oficial" in data["sources"]
