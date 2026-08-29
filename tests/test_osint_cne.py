import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from osint_cne import (
    _classify,
    _normalize_link,
    _parse_avisos_page,
    _parse_news_page,
    cne_lookup,
    get_cne_data,
)

NEWS_HTML = """
<html><body>
<table>
<tr>
  <td class="noticia_fecha">03 de febrero de 2023</td>
  <td><a class="noticia_titulo" href="/web/sala_prensa/noticia_detallada.php?id=4180">Presidente Calzadilla recibe condecoración</a></td>
</tr>
<tr>
  <td class="noticia_fecha">10 de mayo de 2024</td>
  <td><a class="noticia_titulo" href="/web/sala_prensa/noticia_detallada.php?id=4301">CNE convoca a elecciones municipales</a></td>
</tr>
<tr>
  <td class="noticia_fecha">22 de julio de 2024</td>
  <td><a class="noticia_titulo" href="/web/sala_prensa/noticia_detallada.php?id=4402">Resultados del escrutinio por mesa</a></td>
</tr>
</table>
</body></html>
"""

NEWS_HTML_WAYBACK_INJECTED = """
<a class="noticia_titulo" href="/web/20230501000000/https://cne.gov.ve/web/sala_prensa/noticia_detallada.php?id=4180">Noticia archivada</a>
"""

AVISOS_HTML = """
<html><body>
<ul>
<li><a href="/web/sala_prensa/ao_documents/aviso_publico_001.pdf">Aviso público: postulación de candidatos</a></li>
<li><a href="/web/sala_prensa/ao_documents/comunicado_002.pdf">Comunicado oficial del CNE</a></li>
<li><a href="/web/sala_prensa/aviso_003.pdf">Convocatoria a acto público</a></li>
</ul>
</body></html>
"""


def test_parse_news_page():
    items = _parse_news_page(NEWS_HTML, limit=10)
    assert len(items) == 3
    assert items[0]["title"] == "Presidente Calzadilla recibe condecoración"
    assert "noticia_detallada.php" in items[0]["link"]
    assert items[0]["published"] == "03 de febrero de 2023"
    assert items[1]["published"] == "10 de mayo de 2024"
    assert items[2]["title"] == "Resultados del escrutinio por mesa"


def test_parse_news_page_dedup():
    items = _parse_news_page(NEWS_HTML + NEWS_HTML, limit=10)
    titles = [i["title"] for i in items]
    assert len(titles) == len(set(titles))


def test_parse_news_page_empty():
    assert _parse_news_page("") == []
    assert _parse_news_page("<html><body><p>sin noticias</p></body></html>") == []


def test_parse_avisos_page():
    items = _parse_avisos_page(AVISOS_HTML, limit=10)
    assert len(items) == 3
    links = [i["link"] for i in items]
    assert any("ao_documents" in link for link in links)
    assert any(i["title"].startswith("Aviso público") for i in items)


def test_parse_avisos_page_filters_unrelated():
    html = "<a href='/web/estadisticas/indice.php'>Estadísticas</a><a href='/web/sala_prensa/ao_documents/x.pdf'>Aviso</a>"
    items = _parse_avisos_page(html, limit=10)
    assert len(items) == 1


def test_normalize_link_wayback():
    assert _normalize_link("/web/20230501000000/https://cne.gov.ve/web/sala_prensa/noticia_detallada.php?id=4180") == "https://cne.gov.ve/web/sala_prensa/noticia_detallada.php?id=4180"
    assert _normalize_link("/web/sala_prensa/noticia_detallada.php?id=4180") == "https://cne.gov.ve/web/sala_prensa/noticia_detallada.php?id=4180"
    assert _normalize_link("noticia_detallada.php?id=1") == "https://cne.gov.ve/noticia_detallada.php?id=1"
    assert _normalize_link("") == "https://cne.gov.ve"


def test_classify_categories():
    assert _classify({"title": "CNE convoca a elecciones municipales"}) == "convocatoria"
    assert _classify({"title": "Boletín con resultados del escrutinio"}) == "resultados"
    assert _classify({"title": "Nueva resolución de la normativa electoral"}) == "normativa"
    assert _classify({"title": "Comunicado oficial del Consejo Nacional Electoral"}) == "aviso_oficial"
    assert _classify({"title": "Presidente recibe embajada internacional"}) == "institucional_diplomatico"
    assert _classify({"title": "Nota informativa interna"}) == "institucional"


def test_get_cne_data_structure():
    data = get_cne_data()
    assert "timestamp" in data
    assert "sources" in data
    assert "count" in data
    assert "🇻🇪 CNE Comunicados" in data["sources"]


def test_cne_lookup_no_voter_profiling():
    """Institutional lookup must expose institution-level fields, never voter data.
    Skips when the live portal is unreachable (avoids long archive timeouts)."""
    import asyncio

    import requests

    try:
        r = requests.get("https://cne.gov.ve", timeout=5, verify=False)
        reachable = r.status_code == 200
    except Exception:
        reachable = False

    if not reachable:
        pytest.skip("Portal CNE inaccesible desde esta red; lookup integrado omitido.")

    res = asyncio.new_event_loop().run_until_complete(cne_lookup(scope="institucional"))
    assert res["status"] in ("CONSULTADO", "degraded")
    if res["status"] == "CONSULTADO":
        assert res["institucion"].startswith("Consejo Nacional Electoral")
        assert "Registro Electoral fuera de alcance" in res["alcance"]
        assert "comunicados" in res
        assert "avisos_oficiales" in res
        assert "secciones_institucionales" in res
        assert "canal" in res
    else:
        assert "error" in res


def test_parse_cne_voter_html():
    from osint_cne import parse_cne_voter_html

    sample_html = """
    <html>
        <body>
            <table>
                <tr><td>Cédula:</td><td>V-12345678</td></tr>
                <tr><td>Nombre:</td><td>JUAN PEREZ</td></tr>
                <tr><td>Estado:</td><td>MIRANDA</td></tr>
                <tr><td>Municipio:</td><td>SUCRE</td></tr>
                <tr><td>Parroquia:</td><td>PETARE</td></tr>
                <tr><td>Centro:</td><td>ESCUELA BASICA BOLIVARIANA</td></tr>
                <tr><td>Mesa:</td><td>1</td></tr>
            </table>
        </body>
    </html>
    """
    res = parse_cne_voter_html(sample_html)
    assert res is not None
    assert res.get("cedula") == "V-12345678"
    assert res.get("nombre") == "JUAN PEREZ"
    assert res.get("estado") == "MIRANDA"
    assert res.get("centro_votacion") == "ESCUELA BASICA BOLIVARIANA"


def test_cne_voter_wayback_lookup_invalid_format():
    from osint_cne import cne_voter_wayback_lookup

    res = cne_voter_wayback_lookup("INVALID")
    assert res["status"] == "ERROR"
    assert "Formato de cédula inválido" in res["error"]

