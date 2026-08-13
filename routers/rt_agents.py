"""
routers/rt_agents.py — Agent orchestration endpoints extracted from app.py
Rutas: /api/agent/*  (7 endpoints)
"""
import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agents"])


def _get_app_state() -> dict:
    from app import app_state
    return app_state


@router.get("/api/agent/tasks")
async def get_agent_tasks_api(status: str = "", limit: int = 50):
    from agent_orchestrator import orchestrator
    return {"tasks": orchestrator.list_tasks(status=status or None, limit=limit)}


@router.post("/api/agent/approve/{task_id}")
async def approve_agent_task(task_id: str):
    from agent_orchestrator import orchestrator
    ok = orchestrator.approve_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or not in approval state")
    return {"status": "approved"}


@router.post("/api/agent/reject/{task_id}")
async def reject_agent_task(task_id: str):
    from agent_orchestrator import orchestrator
    ok = orchestrator.reject_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or not in approval state")
    return {"status": "rejected"}


@router.get("/api/agent/mode")
async def get_agent_mode():
    from agent_orchestrator import orchestrator
    return {"mode": orchestrator.get_mode()}


@router.post("/api/agent/mode")
async def set_agent_mode(data: dict):
    from agent_orchestrator import orchestrator
    mode = data.get("mode", "suggest")
    orchestrator.set_mode(mode)
    return {"mode": mode}


@router.post("/api/agent/run-cycle")
async def run_agent_cycle():
    """Ejecuta el ciclo de investigación de ARES y genera tareas."""
    from agent_orchestrator import orchestrator
    ctx = _get_app_state().get("context", {})
    await orchestrator.run_investigation_cycle(ctx)
    tasks = orchestrator.list_tasks(status="pending_approval", limit=20)
    return {"status": "cycle_complete", "new_tasks": len(tasks)}


@router.post("/api/agent/run-pending")
async def run_agent_pending():
    """Ejecuta todas las tareas pendientes."""
    from agent_orchestrator import orchestrator
    await orchestrator.run_pending()
    return {"status": "pending_executed"}
