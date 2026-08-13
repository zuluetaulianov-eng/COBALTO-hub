from datetime import date, datetime

import bleach
from bleach.css_sanitizer import CSSSanitizer

# 1. Definir qué estilos CSS son seguros (previene superposiciones maliciosas)
# Bloqueamos explícitamente position, z-index, visibility, opacity extrema, etc.
css_sanitizer = CSSSanitizer(
    allowed_css_properties=[
        "color",
        "background-color",
        "font-weight",
        "text-align",
        "margin",
        "padding",
        "border",
        "border-radius",
        "box-shadow",
        "font-size",
        "font-family",
        "line-height",
    ]
)


def sanitize_html(html_str: str, allow_html: bool = False) -> str:
    """Sanitiza strings HTML. Si allow_html es False, elimina TODAS las etiquetas."""
    if not html_str:
        return ""

    if allow_html:
        allowed_tags = ["b", "i", "strong", "em", "p", "br", "span", "div", "ul", "li", "ol"]
        allowed_attrs = {"span": ["style"], "div": ["style"], "p": ["style"], "*": ["class"]}
        return bleach.clean(
            html_str, tags=allowed_tags, attributes=allowed_attrs, css_sanitizer=css_sanitizer, strip=True
        )
    else:
        # Purga total de HTML para campos estrictos (ej. titles, usernames)
        return bleach.clean(html_str, tags=[], attributes={}, strip=True)


def sanitize_for_json(data, preserve_html_fields=None, current_key=None):
    """Sanitiza recursivamente manteniendo contexto de la llave del diccionario."""
    if preserve_html_fields is None:
        preserve_html_fields = ["text", "consensus", "summary", "description", "global_briefing", "content"]

    if isinstance(data, (datetime, date)):
        return data.isoformat()

    if isinstance(data, str):
        # 2. Verificamos si la llave actual está en la lista de permitidos
        allow_html = current_key in preserve_html_fields
        return sanitize_html(data, allow_html=allow_html)

    elif isinstance(data, list):
        # En listas, heredamos el current_key del contenedor padre
        return [sanitize_for_json(item, preserve_html_fields, current_key) for item in data]

    elif isinstance(data, dict):
        # 3. Propagamos la llave 'k' hacia abajo en la recursión
        return {k: sanitize_for_json(v, preserve_html_fields, current_key=k) for k, v in data.items()}

    return data

