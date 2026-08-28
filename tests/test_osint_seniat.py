import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from osint_seniat import normalize_rif, parse_seniat_response, get_seniat_data, lookup_seniat_rif


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


@pytest.mark.asyncio
async def test_lookup_seniat_rif_empty():
    res = await lookup_seniat_rif("")
    assert res["status"] == "error"


@pytest.mark.asyncio
async def test_lookup_seniat_rif_valid():
    res = await lookup_seniat_rif("J300000001")
    assert "rif" in res
    assert "razon_social" in res
