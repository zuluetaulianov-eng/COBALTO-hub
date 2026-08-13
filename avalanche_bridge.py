import logging
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# APIRouter for Avalanche Pulse compatibility bridge
router = APIRouter(prefix="/avalanche-api", tags=["Avalanche Bridge"])


@router.get("/users/current/")
async def get_current_user():
    """
    Simulates the active operator context for the Avalanche Pulse frontend.
    """
    return JSONResponse(
        {
            "id": 99,
            "username": "operator_cobalto",
            "email": "operator@cobalto.internal",
            "first_name": "Coordinador",
            "last_name": "Táctico",
            "is_staff": True,
            "is_active": True,
            "roles": ["administrator", "analyst"],
            "permissions": ["view_all", "edit_rules", "export_reports"],
        }
    )


@router.get("/projects/")
async def get_projects():
    """
    Maps real statistics and connects tactical cases to the Avalanche Pulse frontend.
    """
    from app import app_state

    ctx = app_state.get("context", {}) or {}
    entries_count = len(ctx.get("all_entries", []))
    alerts_count = len(ctx.get("alerts", []))

    return JSONResponse(
        [
            {
                "id": 101,
                "name": "SitRep Venezuela",
                "description": "Monitoreo consolidado de señales de prensa e información pública regional.",
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "owner": "operator_cobalto",
                "statistics": {
                    "documents_count": entries_count,
                    "sources_count": ctx.get("total_sources", 15),
                    "alerts_count": alerts_count,
                },
            }
        ]
    )


@router.get("/projects/101/")
async def get_project_detail():
    from app import app_state

    ctx = app_state.get("context", {}) or {}
    entries_count = len(ctx.get("all_entries", []))
    alerts_count = len(ctx.get("alerts", []))
    return JSONResponse(
        {
            "id": 101,
            "name": "SitRep Venezuela",
            "description": "Monitoreo consolidado de señales de prensa e información pública regional.",
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "owner": "operator_cobalto",
            "statistics": {
                "documents_count": entries_count,
                "sources_count": ctx.get("total_sources", 15),
                "alerts_count": alerts_count,
            },
        }
    )


@router.get("/lp/blocks/")
async def get_landing_blocks():
    """
    Supplies structural blocks for the analytical main feed widgets.
    """
    return JSONResponse(
        {
            "blocks": [
                {"id": "sitrep", "type": "news_feed", "title": "Reporte de Situación Real", "enabled": True},
                {"id": "intel", "type": "multi_agent", "title": "Consenso de Inteligencia", "enabled": True},
                {"id": "cyber", "type": "soc_monitor", "title": "Alertas SOC & Cyber", "enabled": True},
            ]
        }
    )


@router.get("/rubrics/")
async def get_rubrics():
    """
    Defines classification rules / channels for indexing entries.
    """
    return JSONResponse(
        [
            {"id": 1, "name": "Geopolítica", "code": "geopolitics", "color": "#00e5ff"},
            {"id": 2, "name": "Ciberseguridad", "code": "cyber", "color": "#00ffaa"},
            {"id": 3, "name": "Eventos en Vivo", "code": "live_events", "color": "#ff3b30"},
        ]
    )


@router.get("/settings/")
async def get_settings():
    """
    Supplies customized dashboard UI settings.
    """
    return JSONResponse(
        {
            "theme": "dark",
            "refresh_interval": 300,
            "language": "es",
            "features": {"dossier": True, "social_graph": True, "cyber_monitor": True},
        }
    )


@router.get("/url_map/")
async def get_url_map():
    """
    Map layer initialization assets.
    """
    return JSONResponse(
        {
            "default_lat": 10.5,
            "default_lon": -66.9,
            "default_zoom": 6,
            "layers": [{"name": "OSM", "type": "tile", "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"}],
        }
    )


@router.get("/cards/documents/")
async def get_avalanche_documents():
    """
    Exposes real live Cobalto Hub entries mapped to the Avalanche Pulse Django Rest Framework schema.
    This fully hydrates the Russian OSINT frontend with live, real Venezuelan data!
    """
    from app import app_state

    ctx = app_state.get("context", {}) or {}
    entries = ctx.get("all_entries", []) or []

    docs = []
    for i, entry in enumerate(entries[:100]):
        # Extract host for clean mapping
        url = entry.get("link", "")
        site = "cobalto.internal"
        if url and url.startswith("http"):
            parts = url.split("/")
            if len(parts) > 2:
                site = parts[2]

        # Determine rubric based on content
        rubric_id = 1
        rubric_name = "Geopolítica"
        rubric_code = "geopolitics"

        t = str(entry.get("type", "")).lower()
        if "cyber" in t or "ransomware" in t:
            rubric_id = 2
            rubric_name = "Ciberseguridad"
            rubric_code = "cyber"

        docs.append(
            {
                "id": i + 1,
                "title": entry.get("title", ""),
                "text": entry.get("summary", ""),
                "url": url,
                "published_at": entry.get("published", datetime.now().isoformat()),
                "source": {"id": i + 1, "name": entry.get("source", "COBALTO HUB"), "site": site},
                "rubrics": [{"id": rubric_id, "name": rubric_name, "code": rubric_code}],
                "sentiment": entry.get("sentiment", "neutral"),
                "importance": entry.get("importance", 0.5),
            }
        )

    return JSONResponse({"count": len(docs), "next": None, "previous": None, "results": docs})


@router.get("/documents/")
async def get_avalanche_documents_alt():
    return await get_avalanche_documents()


@router.get("/cards/")
async def get_avalanche_cards():
    return await get_avalanche_documents()


@router.get("/v2/internal/insecure/")
async def get_internal_status():
    """
    Health check response to bypass internal initialization loops.
    """
    return JSONResponse({"status": "operational", "auth_bypass": True, "engine_version": "9.0-cobalto-bridge"})
