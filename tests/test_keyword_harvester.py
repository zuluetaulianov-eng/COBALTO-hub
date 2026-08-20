"""
tests/test_keyword_harvester.py - Pruebas Unitarias para el Motor de Cosecha de Términos Emergentes
"""

import pytest
from keyword_harvester import harvest_emerging_keywords, get_emerging_summary_by_theater


def test_harvest_emerging_keywords_basic():
    keywords = harvest_emerging_keywords(hours_back=48, top_n=5)
    assert isinstance(keywords, list)


def test_get_emerging_summary_by_theater():
    summary = get_emerging_summary_by_theater()
    assert isinstance(summary, dict)
    assert "COL" in summary
    assert "VEN" in summary
    assert "GLOBAL" in summary
