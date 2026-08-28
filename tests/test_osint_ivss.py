import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from osint_ivss import fetch_ivss_noticias, lookup_ivss_individual, get_ivss_data


def test_lookup_ivss_individual_valid():
    res = lookup_ivss_individual("12345678", "V")
    assert res["cedula"] == "V-12345678"
    assert res["nacionalidad"] == "V"
    assert res["status"] == "CONSULTADO"


def test_lookup_ivss_individual_invalid():
    res = lookup_ivss_individual("", "V")
    assert res["status"] == "error"
    assert "error" in res


def test_get_ivss_data_structure():
    data = get_ivss_data()
    assert "timestamp" in data
    assert "sources" in data
    assert "count" in data
    assert "🇻🇪 IVSS Oficial" in data["sources"]
