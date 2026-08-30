import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from osint_seniat import (
    normalize_rif,
    parse_seniat_response,
    get_seniat_data,
    lookup_seniat_rif,
    _classify_news,
    seniat_institucional,
)


def test_normalize_rif():
    assert normalize_rif("J-30000000-1") == ("J", "300000001")
    assert normalize_rif("V12345678") == ("V", "12345678")
    assert normalize_rif("12345678") == ("V", "12345678")


def test_parse_seniat_response():
    html_sample = "<html><body><div>Nombre : EMPRESA EJEMPLO C.A.</div><div>Retención : 75%</div><div>SUJETO PASIVO ESPECIAL</div></body></html>"
    res = parse_seniat_response("J-30000000-1", html_sample)
    assert res["status"] == "CONSULTADO"
    assert res["razon_social"] == "EMPRESA EJEMPLO C.A."
    assert "SUJETO PASIVO ESPECIAL" in res["condicion_iva"]
    assert res["tasa_retencion"] == "75%"


def test_lookup_seniat_rif_empty():
    res = lookup_seniat_rif("")
    assert res["status"] == "error"


def test_lookup_seniat_rif_valid():
    res = lookup_seniat_rif("J300000001")
    assert "rif" in res
    assert "razon_social" in res


def test_classify_news_categories():
    assert _classify_news("Seniat inicia plan de formación para fiscales") == "fiscalizacion"
    assert _classify_news("Seniat presenta nueva identidad visual en su digitalización") == "digitalizacion"
    assert _classify_news("Seniat y la banca privada afianzan alianza") == "banca_y_alianzas"
    assert _classify_news("Comunicado institucional general del Seniat") == "institucional"


def test_seniat_institutional_structure():
    """Ensure institutional lookup never fabricates personal identity data."""
    res = seniat_institucional(scope="institucional", cedula="V-12345678")
    assert res["status"] == "CONSULTADO"
    assert res["alcance"] == "OSINT institucional público — sin perfilamiento de personas naturales"
    doc = res["documento_consultado"]
    assert doc["validacion_formato"]["valida"] is True
    assert "no se consulta" in doc["nota"]


def test_get_seniat_data_structure():
    data = get_seniat_data()
    assert "timestamp" in data
    assert "sources" in data
    assert "count" in data
    assert "🇻🇪 SENIAT Comunicados" in data["sources"]
