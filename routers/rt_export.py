"""
routers/rt_export.py — Export & report generation endpoints extracted from app.py
Rutas: /api/export/sitrep/* (JSON, DOCX, PDF), /api/export/informe-osint/*
Accede a app_state via lazy import.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["export"])


def _sanitize(obj):
    from security_utils import sanitize_for_json
    return sanitize_for_json(obj)


def _get_ctx() -> dict:
    from app import app_state
    return app_state.get("context", {})


# ── SitRep JSON ─────────────────────────────────────────────────────────────

@router.get("/api/export/sitrep")
async def export_sitrep_json():
    """Exporta el SitRep actual como JSON descargable."""
    from dashboard import state

    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    alerts = ctx.get("alerts", []) or []
    network_outages = ctx.get("network_outages", []) or []
    briefing = state.heavy_track_cache.get("global_briefing", {})
    total_sources = ctx.get("total_sources", 0)
    cb_count = 0
    timestamp = datetime.now().isoformat()

    from ai_core import _groq_cb, is_ai_available
    from humanization import STRESS_MONITOR

    sitrep = {
        "sitrep_version": "1.0",
        "generated_at": timestamp,
        "system": {
            "status": "online",
            "total_entries": len(entries),
            "total_alerts": len(alerts),
            "total_sources": total_sources,
            "circuit_breakers_open": cb_count,
            "groq_available": is_ai_available(),
            "groq_circuit_breaker": _groq_cb.__repr__(),
            "stress_level": round(STRESS_MONITOR.scaling_factor, 1),
            "progress": state.progress_state.get("percentage", 0),
            "cycle_id": state.cycle_id,
        },
        "alerts": _sanitize(alerts),
        "network_outages": _sanitize(network_outages),
        "briefing": _sanitize(briefing) if isinstance(briefing, dict) else {},
        "entry_count": len(entries),
        "alert_count": len(alerts),
    }
    return JSONResponse(
        content=sitrep,
        headers={"Content-Disposition": f'attachment; filename="SITREP_COBALTO_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'},
    )


# ── SitRep DOCX ─────────────────────────────────────────────────────────────

@router.get("/api/export/sitrep/docx")
async def export_sitrep_docx():
    """Exporta el SitRep actual como documento Word (.docx)."""
    ctx = _get_ctx()
    from export_sitrep_docx import SitrepDocxError, generate_sitrep_docx
    try:
        doc_bytes = generate_sitrep_docx(ctx)
    except SitrepDocxError as e:
        raise HTTPException(status_code=500, detail=str(e))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="SITREP_COBALTO_{ts}.docx"'},
    )


@router.post("/api/export/sitrep/analizar")
async def analizar_sitrep(request: Request):
    """Analiza entradas del caché con IA Groq. Body: {\"max_entries\": 25}"""
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    max_entries = 25
    try:
        body = await request.json()
        max_entries = int(body.get("max_entries", 25))
    except Exception:
        pass
    from export_sitrep_ia import analizar_entradas_masivo
    to_analyze = _sanitize(entries[:max_entries])
    enriched = await analizar_entradas_masivo(to_analyze)
    return {"status": "ok", "analyzed": len(enriched), "entries": _sanitize(enriched)}


@router.post("/api/export/sitrep/generar-word")
async def generar_sitrep_word(request: Request):
    """Pipeline: analiza entradas con IA + genera Word."""
    max_entries = 25
    try:
        body = await request.json()
        max_entries = int(body.get("max_entries", 25))
    except Exception:
        pass
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    from export_sitrep_docx import SitrepDocxError, generate_sitrep_docx
    from export_sitrep_ia import analizar_entradas_masivo
    to_analyze = _sanitize(entries[:max_entries])
    enriched = await analizar_entradas_masivo(to_analyze)
    enriched_map = {str(e.get("id", e.get("title", ""))): e.get("analysis", {}) for e in enriched}
    for entry in entries:
        eid = str(entry.get("id", entry.get("title", "")))
        if eid in enriched_map:
            entry["analysis"] = enriched_map[eid]
    try:
        doc_bytes = generate_sitrep_docx(ctx)
    except SitrepDocxError as e:
        raise HTTPException(status_code=500, detail=str(e))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="SITREP_COBALTO_IA_{ts}.docx"'},
    )


# ── SitRep PDF ──────────────────────────────────────────────────────────────

@router.get("/api/export/sitrep/pdf")
async def export_sitrep_pdf():
    """Exporta el SitRep actual como PDF via WeasyPrint."""
    ctx = _get_ctx()
    from export_sitrep_pdf import SitrepPDFError, generate_sitrep_pdf
    try:
        pdf_bytes = generate_sitrep_pdf(ctx)
    except SitrepPDFError as e:
        raise HTTPException(status_code=500, detail=str(e))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SITREP_COBALTO_{ts}.pdf"'},
    )


@router.post("/api/export/sitrep/generar-pdf")
async def generar_sitrep_pdf_ia(request: Request):
    """Pipeline: analiza entradas con IA + genera PDF."""
    max_entries = 25
    try:
        body = await request.json()
        max_entries = int(body.get("max_entries", 25))
    except Exception:
        pass
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    from export_sitrep_ia import analizar_entradas_masivo
    from export_sitrep_pdf import SitrepPDFError, generate_sitrep_pdf
    to_analyze = _sanitize(entries[:max_entries])
    enriched = await analizar_entradas_masivo(to_analyze)
    enriched_map = {str(e.get("id", e.get("title", ""))): e.get("analysis", {}) for e in enriched}
    for entry in entries:
        eid = str(entry.get("id", entry.get("title", "")))
        if eid in enriched_map:
            entry["analysis"] = enriched_map[eid]
    try:
        pdf_bytes = generate_sitrep_pdf(ctx)
    except SitrepPDFError as e:
        raise HTTPException(status_code=500, detail=str(e))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SITREP_COBALTO_IA_{ts}.pdf"'},
    )


# ── Informe OSINT DOCX ───────────────────────────────────────────────────────

@router.get("/api/export/informe-osint")
async def export_informe_osint():
    """Exporta el informe OSINT en DOCX (diseño cyber/dark)."""
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    from export_informe_fuentes import cargar_informe
    from export_informe_osint import generar_informe_osint_bytes
    try:
        resultado = cargar_informe(entries=entries, max_docs=20)
        doc_bytes = generar_informe_osint_bytes(resultado.datos)
    except Exception as e:
        logger.error(f"[INFORME OSINT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="INFORME_OSINT_COBALTO_{ts}.docx"'},
    )


@router.post("/api/export/informe-osint/generar-word")
async def generar_informe_osint_word(request: Request):
    """Pipeline completo para el informe OSINT con análisis IA opcional."""
    max_entries = 20
    use_ai = True
    try:
        body = await request.json()
        max_entries = int(body.get("max_entries", 20))
        use_ai = bool(body.get("use_ai", True))
    except Exception:
        pass
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    to_analyze = _sanitize(entries[:max_entries])
    analisis_map: dict = {}
    if use_ai:
        try:
            from export_sitrep_ia import analizar_entradas_masivo
            enriched = await analizar_entradas_masivo(to_analyze)
            for e in enriched:
                eid = str(e.get("id", e.get("title", "")))
                analisis_map[eid] = e.get("analysis", {})
        except Exception as e:
            logger.warning(f"[INFORME OSINT] Análisis IA omitido: {e}")
    from export_informe_osint import build_informe_desde_entries, generar_informe_osint_bytes
    info = build_informe_desde_entries(entries, max_docs=max_entries, analisis_por_entry=analisis_map)
    try:
        doc_bytes = generar_informe_osint_bytes(info)
    except Exception as e:
        logger.error(f"[INFORME OSINT] Error generando DOCX: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="INFORME_OSINT_COBALTO_IA_{ts}.docx"'},
    )
