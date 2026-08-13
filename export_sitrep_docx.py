import io
import json
import logging
import os
import re
from datetime import datetime

from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)

_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "template_sitrep.docx")


class SitrepDocxError(Exception):
    pass


def _sanitizar(texto: str) -> str:
    return _INVALID_XML_RE.sub("", str(texto))


def _build_alerts_context(ctx: dict) -> list:
    alerts_raw = ctx.get("alerts", [])
    if not isinstance(alerts_raw, list):
        return []
    out = []
    for a in alerts_raw[:50]:
        if isinstance(a, dict):
            out.append({
                "type": _sanitizar(str(a.get("type", a.get("tipo", "unknown")))),
                "severity": _sanitizar(str(a.get("severity", a.get("severidad", "info")))),
                "source": _sanitizar(str(a.get("source", a.get("fuente", "")))),
                "timestamp": _sanitizar(str(a.get("timestamp", a.get("time", "")))),
                "title": _sanitizar(str(a.get("title", a.get("titulo", a.get("message", ""))))),
            })
    return out


def _build_outages_context(ctx: dict) -> list:
    outages_raw = ctx.get("events_data", {}).get("network_outages", [])
    if not isinstance(outages_raw, list):
        outages_raw = ctx.get("network_outages", [])
    if not isinstance(outages_raw, list):
        return []
    out = []
    for o in outages_raw[:30]:
        if isinstance(o, dict):
            out.append({
                "asn": _sanitizar(str(o.get("asn", o.get("asn_number", "N/A")))),
                "country": _sanitizar(str(o.get("country", o.get("country_code", "VE")))),
                "drop_percent": _sanitizar(str(o.get("drop_percent", o.get("drop", "0")))),
            })
    return out


def _build_entries_context(ctx: dict) -> list:
    entries_raw = ctx.get("all_entries", [])
    if not isinstance(entries_raw, list):
        return []
    out = []
    for i, e in enumerate(entries_raw[:100]):
        if isinstance(e, dict):
            analysis = e.get("analysis", None)
            analysis_ctx = None
            if isinstance(analysis, dict) and analysis.get("actores"):
                analysis_ctx = {
                    "actores": _sanitizar(", ".join(analysis["actores"]) if isinstance(analysis["actores"], list) else str(analysis["actores"])),
                    "amenaza": _sanitizar(str(analysis.get("amenaza", "Desconocida"))),
                    "analisis": _sanitizar(str(analysis.get("analisis", ""))),
                }
            out.append({
                "idx": str(i + 1),
                "title": _sanitizar(str(e.get("title", e.get("titulo", "Sin titulo")))),
                "source": _sanitizar(str(e.get("source", e.get("fuente", "N/A")))),
                "published": _sanitizar(str(e.get("published", e.get("fecha", "")))),
                "link": _sanitizar(str(e.get("link", e.get("url", "")))),
                "is_crisis": _sanitizar(str(e.get("is_crisis", e.get("crisis", "")))),
                "summary": _sanitizar(str(e.get("summary", e.get("resumen", "")))[:300]),
                "analysis": analysis_ctx,
            })
    return out


def _build_briefing_context(ctx: dict) -> str:
    briefing = ctx.get("global_briefing", {})
    if isinstance(briefing, dict):
        return _sanitizar(json.dumps(briefing, ensure_ascii=False, indent=2))
    return _sanitizar(str(briefing))


def build_sitrep_context(ctx: dict) -> dict:
    alerts = _build_alerts_context(ctx)
    outages = _build_outages_context(ctx)
    entries = _build_entries_context(ctx)
    briefing_raw = ctx.get("global_briefing", {})

    if isinstance(briefing_raw, dict):
        resumen = _sanitizar(str(briefing_raw.get("summary", briefing_raw.get("resumen", ""))))
        briefing = _sanitizar(str(briefing_raw))
    else:
        resumen = _sanitizar(str(briefing_raw))
        briefing = _sanitizar(str(briefing_raw))

    from ai_core import is_ai_available as _check_ai
    from humanization import STRESS_MONITOR

    return {
        "sitrep_version": "1.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "system_status": "ONLINE",
        "cycle_id": _sanitizar(str(ctx.get("cycle_id", "N/A"))),
        "total_entries": str(len(entries)),
        "total_alerts": str(len(alerts)),
        "cb_count": str(ctx.get("cb_count", 0)),
        "total_sources": str(ctx.get("total_sources", 0)),
        "groq_available": "SI" if _check_ai() else "NO",
        "stress_level": str(round(STRESS_MONITOR.scaling_factor, 1)),
        "briefing_resumen": resumen or "Sin resumen disponible",
        "alerts": alerts,
        "outages": outages,
        "entries": entries,
        "briefing": briefing,
    }


def generate_sitrep_docx(ctx: dict) -> bytes:
    if not os.path.exists(_TEMPLATE_PATH):
        raise SitrepDocxError(f"Plantilla no encontrada: {_TEMPLATE_PATH}")

    doc_ctx = build_sitrep_context(ctx)

    try:
        tpl = DocxTemplate(_TEMPLATE_PATH)
        tpl.render(doc_ctx)
    except Exception as e:
        raise SitrepDocxError(f"Error al renderizar plantilla DOCX: {e}")

    buffer = io.BytesIO()
    try:
        tpl.save(buffer)
    except Exception as e:
        raise SitrepDocxError(f"Error al guardar DOCX: {e}")

    buffer.seek(0)
    return buffer.getvalue()
