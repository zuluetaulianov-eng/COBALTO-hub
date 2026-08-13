import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_retriever import (
    _calcular_score_relevancia,
    _extraer_palabras_clave,
    build_rag_prompt,
    retrieve_relevant_entries,
)


def test_extraer_palabras_clave():
    kw = _extraer_palabras_clave("¿Dime qué noticias hay sobre la situación en la frontera de Venezuela?")
    assert "noticias" not in kw
    assert "sobre" not in kw
    assert "frontera" in kw
    assert "venezuela" in kw


def test_calcular_score_relevancia():
    entry = {
        "title": "Conflicto en la frontera de Venezuela",
        "summary": "Se registran incidentes armados en la zona fronteriza.",
        "source": "rss_noticias",
        "entities": ["Venezuela", "Frontera"],
    }
    score = _calcular_score_relevancia(entry, ["frontera", "conflicto"])
    assert score > 5.0


def test_retrieve_relevant_entries():
    sample_entries = [
        {"title": "Noticia sobre elecciones generales", "summary": "Votación en proceso.", "source": "rss1"},
        {"title": "Incidente grave en la frontera", "summary": "Reporte de patrullaje en frontera.", "source": "rss2"},
        {"title": "Economía y tasa cambiaria BCV", "summary": "Informe financiero mensual.", "source": "rss3"},
    ]
    retrieved = retrieve_relevant_entries("incidentes en la frontera", entries=sample_entries, max_docs=2)
    assert len(retrieved) >= 1
    assert "frontera" in retrieved[0]["title"].lower()


def test_build_rag_prompt():
    docs = [
        {"title": "Reporte 1", "source": "fuente_a", "summary": "Resumen 1", "link": "https://a.com"},
        {"title": "Reporte 2", "source": "fuente_b", "summary": "Resumen 2", "link": "https://b.com"},
    ]
    prompt = build_rag_prompt("Situación de seguridad", docs)
    assert "[DOC 1]" in prompt
    assert "[DOC 2]" in prompt
    assert "Reporte 1" in prompt
    assert "Situación de seguridad" in prompt


def test_format_clean_ingestion_prompt():
    from rag_retriever import format_clean_ingestion_prompt
    p = format_clean_ingestion_prompt("texto crudo de prueba")
    assert "[TÍTULO SUGERIDO]" in p
    assert "[RESUMEN SEMÁNTICO]" in p
    assert "[CONTENIDO LIMPIO]" in p
    assert "texto crudo de prueba" in p


def test_kwic_search():
    from historical_store import kwic_search, store_entries
    sample_entry = {
        "title": "Prueba de concordancia KWIC",
        "summary": "Este informe analiza la seguridad en la frontera sur de la región.",
        "source": "test_kwic",
        "link": "https://test.com/kwic1",
        "published": "2026-08-12T10:00:00"
    }
    store_entries([sample_entry])
    res = kwic_search("frontera", window_words=3, limit=5)
    assert isinstance(res, list)
    if res:
        assert res[0]["keyword"].lower() == "frontera"

