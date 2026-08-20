"""
routers/rt_humint.py — HUMINT endpoints extracted from app.py
Rutas: /api/humint/*  (7 endpoints)
"""
import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["humint"])


def _sanitize(obj):
    from security_utils import sanitize_for_json
    return sanitize_for_json(obj)


@router.get("/api/humint/reports")
async def get_humint_reports(limit: int = 50, status: str = "", severity: str = ""):
    from humint_bot import get_reports
    reports = get_reports(limit=limit, status=status, severity=severity)
    return _sanitize({"reports": reports})


@router.get("/api/humint/report/{report_id}")
async def get_humint_report(report_id: str):
    from humint_bot import get_report
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _sanitize(report)


@router.post("/api/humint/report")
async def create_humint_report(data: dict):
    from humint_bot import store_report
    rid = store_report(
        source=data.get("source", "api"),
        reporter=data.get("reporter", ""),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        location_name=data.get("location_name", ""),
        title=data.get("title", ""),
        description=data.get("description", ""),
        photo_url=data.get("photo_url", ""),
        tags=data.get("tags", []),
        severity=data.get("severity", "info"),
    )
    return {"status": "created", "id": rid}


@router.post("/api/humint/report/{report_id}/status")
async def update_humint_status(report_id: str, data: dict):
    from humint_bot import update_status
    new_status = data.get("status", "reviewed")
    ok = update_status(report_id, new_status)
    return {"status": "updated" if ok else "not_found"}


@router.get("/api/humint/stats")
async def get_humint_stats():
    from humint_bot import get_stats
    return _sanitize(get_stats())


@router.post("/api/humint/cycle")
async def run_humint_cycle_api():
    from humint_bot import run_humint_cycle
    count = await run_humint_cycle()
    return {"published": count}
