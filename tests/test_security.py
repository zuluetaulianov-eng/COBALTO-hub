"""Test de seguridad y sanitización."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sanitize_html():
    from security_utils import sanitize_html

    dirty = "<script>alert('xss')</script><b>bold</b>"
    clean = sanitize_html(dirty, allow_html=False)
    assert "<script>" not in clean
    assert "<b>" not in clean

    clean_with_tags = sanitize_html(dirty, allow_html=True)
    assert "<script>" not in clean_with_tags
    assert "<b>" in clean_with_tags


def test_sanitize_for_json():
    from security_utils import sanitize_for_json

    data = {
        "title": "<script>alert(1)</script>",
        "text": "<b>safe</b>",
        "nested": {"content": "<img src=x onerror=alert(1)>"},
    }
    result = sanitize_for_json(data)
    assert "<script>" not in result["title"]
    assert "<b>" in result["text"]
    assert "onerror" not in result["nested"]["content"]


def test_auth_validation():
    import os

    os.environ["ADMIN_PASSWORD"] = "secure_pass_123"
    os.environ["JWT_SECRET"] = "test-secret-for-jwt"
    import importlib

    import app_auth

    importlib.reload(app_auth)

    wrong_tokens = ["", "invalid", "a.b", "eyJ.eyJ9.signature"]
    for t in wrong_tokens:
        payload = app_auth.verify_token(t)
        assert payload == {}, f"Token '{t}' no fue rechazado"
