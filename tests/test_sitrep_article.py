import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers.rt_sitrep import clean_plain_text, extract_article_from_html, is_safe_article_url


def test_extract_article_from_html():
    html = """
    <html>
      <head>
        <title>Titulo corto</title>
        <meta property="og:title" content="Operativo en frontera">
        <meta property="og:description" content="Resumen largo de la noticia">
        <meta name="author" content="Redaccion">
        <meta property="og:site_name" content="Fuente OSINT">
        <meta property="og:image" content="https://example.com/foto.jpg">
      </head>
      <body>
        <nav>Menu basura</nav>
        <article>
          <p>Las fuerzas de seguridad desplegaron un operativo en la frontera norte.</p>
          <p>Se reportaron retenciones y controles adicionales durante la madrugada.</p>
          <p>Fuentes locales confirman movimiento de unidades y cierre parcial de pasos.</p>
        </article>
      </body>
    </html>
    """
    data = extract_article_from_html(html, "https://example.com/nota")
    assert data["ok"] is True
    assert data["title"] == "Operativo en frontera"
    assert "operativo" in data["content"].lower()
    assert data["author"] == "Redaccion"
    assert data["image"] == "https://example.com/foto.jpg"
    assert data["word_count"] > 10


def test_clean_plain_text_strips_code_and_html():
    raw = """
    <script>alert(1)</script>
    <p>Las tropas avanzaron al amanecer.</p>
    function() { var x = 1; }
    Compartir en Facebook
    <div class="share">WhatsApp</div>
    """
    text = clean_plain_text(raw)
    assert "<" not in text
    assert "script" not in text.lower()
    assert "function" not in text.lower()
    assert "facebook" not in text.lower()
    assert "tropas avanzaron" in text.lower()


def test_extract_ignores_widgets_and_scripts():
    html = """
    <html><body>
      <article>
        <script>window.dataLayer = [];</script>
        <style>.foo { color: red; }</style>
        <p>Informe táctico del operativo fronterizo confirmado por fuentes locales.</p>
        <div class="share">Compartir en Twitter</div>
        <p>Se registró movimiento de unidades durante la madrugada en el eje norte.</p>
      </article>
    </body></html>
    """
    data = extract_article_from_html(html, "https://example.com/nota")
    assert "<" not in data["content"]
    assert "dataLayer" not in data["content"]
    assert "color: red" not in data["content"]
    assert "compartir" not in data["content"].lower()
    assert "operativo fronterizo" in data["content"].lower()


def test_is_safe_article_url_rejects_local():
    assert is_safe_article_url("http://127.0.0.1/x") is False
    assert is_safe_article_url("file:///etc/passwd") is False
    assert is_safe_article_url("javascript:alert(1)") is False
    assert is_safe_article_url("") is False
