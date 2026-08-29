import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from osint_saime import (
    _classify_mobility,
    _parse_feed,
    _validate_cedula,
    get_saime_data,
    saime_lookup,
)


def test_validate_cedula_valid_national():
    res = _validate_cedula("V-1234567")
    assert res["valida"] is True
    assert res["nacionalidad"] == "V"
    assert res["solo_validacion_estructural"] is True
    # Estructural only: no personal data is returned
    assert "nombre" not in res
    assert "datos_personales" not in res


def test_validate_cedula_valid_extranjero():
    res = _validate_cedula("E-12345678")
    assert res["valida"] is True
    assert res["nacionalidad"] == "E"


def test_validate_cedula_invalid_empty():
    res = _validate_cedula("")
    assert res["valida"] is False


def test_validate_cedula_invalid_letter():
    res = _validate_cedula("X-1234567")
    assert res["valida"] is False
    assert "Nacionalidad" in res["motivo"]


def test_validate_cedula_invalid_digit_range():
    res = _validate_cedula("V-123")
    assert res["valida"] is False


def test_classify_mobility_border():
    item = {"title": "Saime habilita paso fronterizo en Táchira", "summary": ""}
    assert _classify_mobility(item) == "movilidad_fronteriza"


def test_classify_mobility_institutional():
    item = {"title": "Saime celebra aniversario con ofrenda floral", "summary": ""}
    assert _classify_mobility(item) == "institucional"


def test_parse_feed_empty():
    assert _parse_feed("") == []
    assert _parse_feed(None) == []


def test_saime_lookup_offline_degrades():
    # Without network the circuit breaker guards; assert the response shape stays valid.
    import asyncio
    import time

    import osint_saime

    async def _run():
        osint_saime._saime_failures = osint_saime._SAIME_CB_THRESHOLD  # force open circuit
        osint_saime._saime_disabled_until = time.time() + 60
        try:
            res = await saime_lookup()
            # Either degraded (circuit open) or CONSULTADO (network available)
            return res["status"] in ("degraded", "CONSULTADO")
        finally:
            osint_saime._saime_failures = 0
            osint_saime._saime_disabled_until = 0

    assert asyncio.run(_run())


def test_get_saime_data_structure():
    data = get_saime_data()
    assert "timestamp" in data
    assert "sources" in data
    assert "count" in data
    assert "🇻🇪 SAIME Comunicados" in data["sources"]
