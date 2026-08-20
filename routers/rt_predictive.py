"""
routers/rt_predictive.py — Predictive scoring & early warning endpoints extracted from app.py
Rutas: /api/predictive/*  (4 endpoints)
Nota: /api/predictive/run accede a app_state via import lazy.
"""
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predictive"])


def _sanitize(obj):
    from security_utils import sanitize_for_json
    return sanitize_for_json(obj)


def _get_app_state() -> dict:
    """Lazy import de app_state para evitar circular imports."""
    from app import app_state
    return app_state


@router.get("/api/predictive/alerts")
async def get_predictive_alerts(include_resolved: bool = False, limit: int = 50):
    from early_warning import early_warning
    if include_resolved:
        alerts = early_warning.get_history(limit=limit)
    else:
        alerts = early_warning.get_active()
    return _sanitize({"alerts": alerts})


@router.post("/api/predictive/resolve/{entity_id}")
async def resolve_predictive_alert(entity_id: str):
    from early_warning import early_warning
    ok = early_warning.resolve(entity_id)
    return {"status": "resolved" if ok else "not_found"}


@router.get("/api/predictive/stats")
async def get_predictive_stats():
    from early_warning import early_warning
    stats = early_warning.get_stats()
    try:
        from entity_registry import get_stats as ent_stats
        es = await asyncio.to_thread(ent_stats)
        stats["entities"] = es
    except Exception:
        stats["entities"] = {}
    return stats


@router.get("/api/predictive/run")
async def run_predictive_cycle():
    """Trigger a predictive scoring cycle manually."""
    from agent_orchestrator import orchestrator
    from dashboard import get_dashboard_data
    from early_warning import early_warning
    from entity_registry import list_all as list_entities
    from event_bus import bus
    from predictive_scorer import compute_entity_threat

    entities = await asyncio.to_thread(list_entities, limit=200)
    if not entities:
        from backfill_entities import backfill_from_historical_store, backfill_from_sanctions
        await asyncio.to_thread(backfill_from_sanctions)
        await asyncio.to_thread(backfill_from_historical_store)
        entities = await asyncio.to_thread(list_entities, limit=200)
        if not entities:
            return _sanitize({
                "status": "no_entities",
                "message": "No hay entidades en el registro. El backfill no encontró datos.",
            })

    agent_findings = [t for t in orchestrator.list_tasks(status="completed") if t.get("result")]
    ctx = (await get_dashboard_data()) or {}
    composite_events = ctx.get("composite_events", [])
    all_entries = ctx.get("all_entries", [])

    now = datetime.now()
    scores = []
    for ent in entities:
        try:
            sc = compute_entity_threat(ent, agent_findings, composite_events, all_entries, now)
            scores.append(sc)
        except Exception:
            continue

    scores.sort(key=lambda x: x["threat_score"], reverse=True)

    new_warnings = early_warning.evaluate(scores, context=ctx)
    for w in new_warnings:
        bus.emit("predictive", source="predictive_scorer", data={
            "warning": w,
            "summary": f"{w['level']}: {w['entity_name']} (score={w['threat_score']})",
        })

    return _sanitize({
        "scores": scores[:50],
        "new_warnings": len(new_warnings),
        "total_active": len(early_warning.get_active()),
    })
