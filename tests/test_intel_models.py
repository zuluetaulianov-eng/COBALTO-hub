"""
tests/test_intel_models.py
Tests para los modelos Pydantic de static_intel.json.
Verifica validación estricta, fallbacks, merge de campos y load_static_intel().
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.intel_models import (
    NotaInformativa,
    OwnPost,
    StaticIntelFile,
    load_static_intel,
)


# ── OwnPost ──────────────────────────────────────────────────────────────────

def test_own_post_minimal_valid():
    """Un OwnPost con solo los campos obligatorios debe ser válido."""
    post = OwnPost(title="Alerta Táctica", comment_short="Resumen del evento.")
    assert post.title == "Alerta Táctica"
    assert post.comment_short == "Resumen del evento."
    assert post.source == "COBALTO INTEL"
    assert post.severity == "info"
    assert post.type == "own"
    assert isinstance(post.tags, list)


def test_own_post_comment_filled_from_short():
    """Si comment está vacío, debe heredar el valor de comment_short."""
    post = OwnPost(title="Test", comment_short="Texto corto de prueba.")
    assert post.comment == "Texto corto de prueba."


def test_own_post_comment_preserved_when_given():
    """Si comment está presente, no debe ser sobrescrito por comment_short."""
    post = OwnPost(
        title="Test",
        comment_short="Corto",
        comment="Texto completo mucho más largo.",
    )
    assert post.comment == "Texto completo mucho más largo."


def test_own_post_severity_levels():
    """Todos los niveles de severidad válidos deben aceptarse."""
    for level in ("info", "atencion", "urgente", "critico"):
        post = OwnPost(title="Prueba nivel", comment_short="Resumen de prueba.", severity=level)
        assert post.severity == level


def test_own_post_invalid_severity():
    """Un nivel de severidad desconocido debe generar ValidationError."""
    with pytest.raises(Exception):  # pydantic.ValidationError
        OwnPost(title="X", comment_short="Y", severity="extremo")


def test_own_post_title_too_short():
    """Título con menos de 3 caracteres debe fallar."""
    with pytest.raises(Exception):
        OwnPost(title="AB", comment_short="Texto válido para prueba.")


def test_own_post_whitespace_stripped():
    """Los espacios en blanco de title y comment_short deben ser eliminados."""
    post = OwnPost(title="  Título con espacios  ", comment_short="  Resumen.  ")
    assert post.title == "Título con espacios"
    assert post.comment_short == "Resumen."


def test_own_post_tags_normalized():
    """Los tags deben ser convertidos a lista de strings."""
    post = OwnPost(title="Test", comment_short="Texto", tags=["política", "fanb", 123])
    assert post.tags == ["política", "fanb", "123"]


def test_own_post_tags_none_becomes_empty_list():
    """tags=None debe convertirse a lista vacía."""
    post = OwnPost(title="Test", comment_short="Texto", tags=None)
    assert post.tags == []


def test_own_post_serialization():
    """model_dump() debe retornar un dict con todos los campos esperados."""
    post = OwnPost(title="Test", comment_short="Corto", tags=["tag1"])
    d = post.model_dump()
    assert isinstance(d, dict)
    for key in ("title", "comment_short", "comment", "source", "published", "link", "tags", "severity", "type"):
        assert key in d


# ── NotaInformativa ──────────────────────────────────────────────────────────

def test_nota_informativa_valid():
    """Una NotaInformativa con campos obligatorios debe ser válida."""
    nota = NotaInformativa(title="Nota editorial", body="Contenido de la nota.")
    assert nota.title == "Nota editorial"
    assert nota.body == "Contenido de la nota."
    assert nota.author == "COBALTO"
    assert nota.pinned is False


def test_nota_informativa_title_too_short():
    """Título con menos de 3 caracteres debe fallar."""
    with pytest.raises(Exception):
        NotaInformativa(title="AB", body="Contenido válido.")


def test_nota_informativa_pinned():
    """El campo pinned debe aceptar True/False."""
    nota = NotaInformativa(title="Urgente", body="Texto.", pinned=True)
    assert nota.pinned is True


# ── StaticIntelFile ──────────────────────────────────────────────────────────

def test_static_intel_file_empty():
    """Un archivo vacío debe producir listas vacías."""
    f = StaticIntelFile(OWN_POSTS=[], NOTES_INFORMATIVAS=[])
    assert f.OWN_POSTS == []
    assert f.NOTES_INFORMATIVAS == []


def test_static_intel_file_with_entries():
    """El schema raíz debe validar listas de posts y notas."""
    f = StaticIntelFile(
        OWN_POSTS=[{"title": "Post test", "comment_short": "Resumen del post de prueba."}],
        NOTES_INFORMATIVAS=[{"title": "Nota test", "body": "Cuerpo de la nota."}],
    )
    assert len(f.OWN_POSTS) == 1
    assert len(f.NOTES_INFORMATIVAS) == 1
    assert isinstance(f.OWN_POSTS[0], OwnPost)


# ── load_static_intel() ──────────────────────────────────────────────────────

def test_load_static_intel_valid_file():
    """load_static_intel() debe cargar y validar un archivo válido."""
    data = {
        "OWN_POSTS": [
            {"title": "Alerta real", "comment_short": "Resumen de la alerta para prueba."}
        ],
        "NOTES_INFORMATIVAS": [
            {"title": "Nota informativa", "body": "Cuerpo de la nota informativa."}
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        path = f.name

    try:
        posts, notes = load_static_intel(path)
        assert len(posts) == 1
        assert len(notes) == 1
        assert posts[0]["title"] == "Alerta real"
        assert notes[0]["title"] == "Nota informativa"
        # Debe ser un dict plano (compatibilidad backward)
        assert isinstance(posts[0], dict)
    finally:
        os.unlink(path)


def test_load_static_intel_missing_file():
    """Si el archivo no existe, retorna ([], []) sin lanzar excepción."""
    posts, notes = load_static_intel("/ruta/inexistente/static_intel.json")
    assert posts == []
    assert notes == []


def test_load_static_intel_invalid_json():
    """Si el JSON está malformado, retorna ([], []) sin lanzar excepción."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write("{esto no es JSON válido...")
        path = f.name

    try:
        posts, notes = load_static_intel(path)
        assert posts == []
        assert notes == []
    finally:
        os.unlink(path)


def test_load_static_intel_partial_invalid():
    """Entradas inválidas son omitidas; las válidas se cargan correctamente."""
    data = {
        "OWN_POSTS": [
            {"title": "Válido", "comment_short": "Resumen de la alerta táctica válida."},
            {"title": "X", "comment_short": "Corto"},  # title demasiado corto → inválido
            {"comment_short": "Sin título"},            # falta title → inválido
        ],
        "NOTES_INFORMATIVAS": [],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        path = f.name

    try:
        posts, notes = load_static_intel(path)
        # Solo el primero debe pasar
        assert len(posts) == 1
        assert posts[0]["title"] == "Válido"
        assert notes == []
    finally:
        os.unlink(path)


def test_load_static_intel_empty_file():
    """Un JSON vacío {} retorna ([], []) sin error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({}, f)
        path = f.name

    try:
        posts, notes = load_static_intel(path)
        assert posts == []
        assert notes == []
    finally:
        os.unlink(path)
