"""
routers/rt_entities.py — Entity Registry endpoints extracted from app.py
Rutas: /api/entities/*  (5 endpoints)
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["entities"])


def _sanitize(obj):
    from security_utils import sanitize_for_json
    return sanitize_for_json(obj)


@router.get("/api/entities/stats")
async def entities_stats_api():
    """Entity registry statistics."""
    from entity_registry import get_stats
    return _sanitize(await asyncio.to_thread(get_stats))


@router.get("/api/entities/search")
async def get_entities_search_api(
    q: str = "",
    type: str = "",
    source: str = "",
    ofac_only: bool = False,
    limit: int = 100,
):
    """Search entities in the registry."""
    from entity_registry import get_ofac_matched, search
    if ofac_only:
        results = await asyncio.to_thread(get_ofac_matched, limit=limit)
    else:
        results = await asyncio.to_thread(
            search, query=q, entity_type=type or None, source=source or None, limit=limit
        )
    return _sanitize({"entities": results})


@router.get("/api/entities/{entity_id}")
async def get_entity_api(entity_id: str):
    """Get a single entity by ID."""
    from entity_registry import get_by_id
    entity = await asyncio.to_thread(get_by_id, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _sanitize(entity)


@router.post("/api/entities/backfill")
async def backfill_entities_api():
    """Poblar entity registry desde OFAC SDN y datos históricos."""
    from backfill_entities import (
        backfill_from_historical_store,
        backfill_from_sanctions,
    )
    s_count = await asyncio.to_thread(backfill_from_sanctions)
    h_count = await asyncio.to_thread(backfill_from_historical_store)
    total = (s_count or 0) + (h_count or 0)
    return {
        "status": "ok",
        "from_sanctions": s_count or 0,
        "from_historical": h_count or 0,
        "total": total,
        "message": f"Entidades pobladas: {total} ({s_count or 0} de OFAC, {h_count or 0} de históricos)",
    }
