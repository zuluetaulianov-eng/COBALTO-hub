import io
import os
import re

import httpx
from docx.shared import Inches
from docxtpl import DocxTemplate, InlineImage
from httpx import HTTPError, TimeoutException

from backend.config import settings
from backend.models.reporte import ReporteRequest

_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def _sanitizar(texto: str) -> str:
    return _INVALID_XML_RE.sub("", str(texto))

_http_client: httpx.AsyncClient | None = None

def set_http_client(client: httpx.AsyncClient):
    global _http_client
    _http_client = client

async def _get_client() -> httpx.AsyncClient:
    if _http_client is None:
        raise RuntimeError(
            "httpx.AsyncClient no inicializado. "
            "Debe llamarse set_http_client() antes de usar el servicio."
        )
    return _http_client

class DocxGenerationError(Exception):
    pass

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "template_reporte.docx")

async def generar_documento_word(payload: ReporteRequest, analisis_por_novedad: list[dict]) -> bytes:
    if not os.path.exists(_TEMPLATE_PATH):
        raise DocxGenerationError(f"No se encontró la plantilla en {_TEMPLATE_PATH}")

    tpl = DocxTemplate(_TEMPLATE_PATH)

    novedades_context = []

    for novedad, analisis in zip(payload.novedades, analisis_por_novedad):
        actores = ", ".join(analisis.get("actores", [])) if isinstance(analisis.get("actores"), list) else str(analisis.get("actores", "No identificados"))
        if not actores.strip():
            actores = "No identificados"

        nov_dict = {
            "fecha": _sanitizar(novedad.fecha_situacion),
            "url": _sanitizar(str(novedad.portal_web_url)),
            "texto": _sanitizar(novedad.texto_situacion),
            "actores": _sanitizar(actores),
            "amenaza": _sanitizar(str(analisis.get("amenaza", "Desconocida"))),
            "analisis": _sanitizar(analisis.get("analisis", "")),
            "imagenes": []
        }

        for img in novedad.imagenes:
            if not img.url:
                continue
            client = await _get_client()
            try:
                img_response = await client.get(str(img.url))
                img_response.raise_for_status()

                content_type = img_response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    continue
            except (HTTPError, TimeoutException):
                continue

            image_stream = io.BytesIO(img_response.content)
            try:
                inline_img = InlineImage(tpl, image_stream, width=Inches(settings.image_max_width_inches))
            except Exception:
                continue

            nov_dict["imagenes"].append({
                "inline": inline_img,
                "descripcion": _sanitizar(img.descripcion) if img.descripcion else ""
            })

        novedades_context.append(nov_dict)

    context = {"novedades": novedades_context}

    try:
        tpl.render(context)
    except Exception as e:
        raise DocxGenerationError(f"Error al renderizar la plantilla: {str(e)}")

    buffer = io.BytesIO()
    try:
        tpl.save(buffer)
    except Exception as e:
        raise DocxGenerationError(f"Error al guardar el documento Word: {str(e)}")

    buffer.seek(0)
    return buffer.getvalue()
