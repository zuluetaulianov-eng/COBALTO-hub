import asyncio

from fastapi import APIRouter, Query

from backend.models.osint import OsintSearchParams
from backend.services import osint_service

router = APIRouter(prefix="/api/osint", tags=["OSINT"])


@router.get("/entries", response_model=dict)
async def get_entries(
    tag: str = Query(None, description="Filtrar por categoría"),
    q: str = Query(None, description="Búsqueda por texto"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    params = OsintSearchParams(tag=tag, q=q, limit=limit, offset=offset)
    entradas, total = await asyncio.gather(
        osint_service.listar_entradas(params),
        osint_service.contar_entradas(params),
    )
    return {
        "data": [e.model_dump() for e in entradas],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tags", response_model=list[str])
async def get_tags():
    return await osint_service.listar_tags()
