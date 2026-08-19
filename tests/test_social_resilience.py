# tests/test_social_resilience.py - Tests para resiliencia OSINT y deduplicación canónica
import sys
from pathlib import Path

# Insertar el directorio raíz en sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from social_hub import canonicalize_url, is_duplicate
from social_public_extractor import REDDIT_FRONTEND_INSTANCES


def test_canonicalize_url():
    """Verifica que URLs equivalentes de distintas fuentes devuelvan la misma clave canónica."""
    url1 = "https://redlib.catsarch.com/r/vzla/comments/123abc4/noticia_de_prueba?utm_source=rss"
    url2 = "https://www.reddit.com/r/vzla/comments/123abc4/noticia_de_prueba/"
    url3 = "http://reddit.com/r/vzla/comments/123abc4/noticia_de_prueba"

    c1 = canonicalize_url(url1)
    c2 = canonicalize_url(url2)
    c3 = canonicalize_url(url3)

    assert c1 == "reddit.com/r/vzla/comments/123abc4/noticia_de_prueba"
    assert c2 == "reddit.com/r/vzla/comments/123abc4/noticia_de_prueba"
    assert c3 == "reddit.com/r/vzla/comments/123abc4/noticia_de_prueba"


def test_is_duplicate_canonical():
    """Verifica la deduplicación a través de URLs canónicas distintas en formato pero idénticas en contenido."""
    item1 = {
        "title": "Noticia Importante en Venezuela",
        "link": "https://redlib.vlink.dev/r/vzla/comments/999xyz/noticia",
    }
    item2 = {
        "title": "Noticia Importante en Venezuela",
        "link": "https://www.reddit.com/r/vzla/comments/999xyz/noticia/",
    }

    # El primero no debe ser duplicado
    assert is_duplicate(item1) is False
    # El segundo DEBE ser identificado como duplicado gracias a canonicalize_url
    assert is_duplicate(item2) is True


def test_redlib_frontend_pool():
    """Verifica que existan múltiples instancias de Redlib en el pool dinámico."""
    assert len(REDDIT_FRONTEND_INSTANCES) >= 3
    assert any("redlib" in inst or "libreddit" in inst for inst in REDDIT_FRONTEND_INSTANCES)
